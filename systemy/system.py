from abc import ABC, abstractmethod
from enum import Enum
from pydantic import create_model, Field, BaseModel
import weakref 
from typing import Any, Dict, Generic, Iterable, List, Optional, Tuple, Type, TypeVar, get_type_hints
from collections import UserDict, UserList

from pydantic.config import Extra
from pydantic.error_wrappers import ValidationError
from pydantic.fields import ModelField, PrivateAttr



class MemberType(Enum):
    FactoryList = "list"
    FactoryDict = "dict"
    Factory = "factory"
    Other = "other"

def _get_field_type(field)->MemberType:
    if isinstance(field.type_, type) and issubclass( field.type_, BaseFactory):
        if issubclass( field.type_, FactoryDict): return MemberType.FactoryDict 
        if issubclass( field.type_, FactoryList): return MemberType.FactoryList


        if field.sub_fields:
            if field.key_field:
                if issubclass( field.sub_fields[0].type_, BaseFactory): 

                    return MemberType.FactoryDict
                else:
                    return MemberType.Other 


            else:
                if issubclass( field.sub_fields[0].type_, BaseFactory): 
                    return MemberType.FactoryList
        else:
            if isinstance(field.type_, type) and issubclass( field.type_, BaseFactory):
                return MemberType.Factory
            return MemberType.Other 

    else:
        return MemberType.Other
    

def _class_to_model_args(Cls: Type) -> dict:
    """ return dictionary of argument for a model creation and from regular class """     
    type_hints = get_type_hints(Cls)
    kwargs = {}
    for name, val in Cls.__dict__.items():
        if name.startswith("_"): continue 
        if name in type_hints:
            kwargs[name] = (type_hints[name], val)
        else:
            kwargs[name] = val 
    for name, hint in type_hints.items():
        if name.startswith("_"): continue
        if name not in kwargs:
            kwargs[name] = (hint, Field(...))
    return kwargs



def join_path(*args) -> str:
    """ join key elements """
    return ".".join(a for a in args if a)


class BaseFactory(BaseModel, ABC):
    __parent_attribute_name__ = PrivateAttr(None)
    
    class Config: #pydantic config  
        extra = Extra.forbid
    
    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # FactoryList is declared after. Is it acceptable to do like this ? 
        try:
            FactoryList
        except NameError:
            return 
        # Mutate normal list or dict of Factory into FactoryList or FactoryDict
        for name, field in cls.__fields__.items():
            field_type = _get_field_type(field)
        
            if field_type == MemberType.FactoryDict:
                if field.default is not None and not isinstance(  field.default, FactoryDict ):
                    if issubclass( field.type_, FactoryDict):
                        field.default = field.type_( field.default )
                    # else:
                    elif issubclass( field.type_, dict) :

                        raise ValueError(f"Hey Dict!!!!! {field.type_} {field.default}" )
            elif field_type == MemberType.FactoryList:
                if field.default is not None and not isinstance(  field.default, FactoryList ):
                    if issubclass( field.type_, FactoryList):
                        field.default = field.type_( field.default )
                    elif issubclass( field.type_, list) :
                        
                        raise ValueError(f"Hey List !!!!! {field.type_} {field.default}")

    @classmethod
    def get_system_class(cls):
        raise ValueError("This factory is not associated to a single System class")


    @abstractmethod 
    def build(self, parent=None, path=None) -> "BaseSystem":
        """ Build the system object """
    
    def update(self, __d__=None, **kwargs):
        if __d__: 
            kwargs = dict(__d__, **kwargs)
        
        validate_assignment_state = self.__config__.validate_assignment
        try:
            self.__config__.validate_assignment = True 
            for key, value in kwargs.items():
                setattr( self, key, value)
        finally:
            self.__config__.validate_assignment = validate_assignment_state

    def __get__(self, parent, cls=None):
        if parent is None:
            return self 
        if self.__parent_attribute_name__:
            return  self._build_and_save_in_parent(parent, self.__parent_attribute_name__)
        raise RuntimeError("attribute name is unknwon")
    
    def _build_and_save_in_parent(self, parent, name):
        try:
            system = parent.__dict__[name]
        except KeyError:
            system = self.build(parent, name)
            parent.__dict__[name] = system
        return system
    
    @classmethod
    def _make_new_path(cls, parent: Optional["BaseSystem"], name: str):
        """ return a new path from a parent system and a name """
        if parent:
            path = join_path(parent.__path__, name)
        else:
            path = name or ""
        return path
    
    def __set_name__(self, owner, name):
        self.__parent_attribute_name__ = name
        # self.__dict__['__parent_attribute_name__'] = name


class BaseConfig(BaseFactory):
    class Config:
        extra = Extra.forbid

    @staticmethod
    def __parent_system_class_ref__():
        # This will be overwriten when included in the System Class 
        return None 

    @classmethod
    def get_system_class(cls):
       System = cls.__parent_system_class_ref__()
       if System is None:
           raise ValueError("This Config class is not associated to any System")
       return System 
    
    def build(self, parent: "BaseSystem" = None, name="") -> "BaseSystem":
        """ Build a System class from this configuration """
        System = self.get_system_class()
        return System(__config__ =self, __path__ = self._make_new_path(parent, name))



class FactoryDictMeta(type(BaseModel)):
    def __getitem__(cls, items):
        if (len(items)!=2):
            raise ValueError(f"expected 2  parameters for FactoryDict[k,f]; actual {len(items)} ")
        Key, Factory = items 
        if not issubclass( Factory, BaseFactory):
            raise ValueError( "expecting a subclass of BaseFactory for FactoryList" )
        return create_model( cls.__name__+"Customized", __base__=cls, __root__=(Dict[Key, Factory], ...))

class FactoryDict(BaseFactory, UserDict,  metaclass=FactoryDictMeta ):
    __root__: Dict[str, BaseFactory] = {}
    __Factory__ = None
    def __init__(self, __root__=None, __Factory__=BaseFactory):
        if __root__ is None:
            __root__ = {}
        super().__init__(__root__=__root__)
        self.__dict__['__Factory__'] = __Factory__

    @classmethod 
    def get_system_class(cls):
        return SystemDict
    @property
    def data(self):
        return self.__root__
    def __iter__(self):
        return UserDict.__iter__(self)
    def __setitem__(self, key, value):
        if not isinstance(value, self.__Factory__):
            raise KeyError( f'item {key} is not a {self.__Factory__.__name__}')
    def build(self, parent=None, name="") -> "SystemDict":
        system_dict =  SystemDict( 
                {key:factory.build(parent, name+"['"+str(key)+"']") for key,factory in self.items() }
                )
        if parent:
            system_dict.__get_parent__ = weakref.ref(parent) 
        return system_dict 


class FactoryListMeta(type(BaseModel)):
    def __getitem__(cls, items):
        if isinstance(items, tuple) and (len(items)!=1):
            raise ValueError(f"expected 1  parameters for FactoryList[f]; actual {len(items)} ")
        Factory = items 
        if not issubclass( Factory, BaseFactory):
            raise ValueError( "expecting a subclass of BaseFactory for FactoryList" )
        return create_model( cls.__name__+"Customized", __base__=cls, __root__=(List[Factory], ...))

class FactoryList(BaseFactory, UserList, metaclass=FactoryListMeta):
    __root__: List[BaseFactory] = []
    __Factory__ = None
    def __init__(self, __root__=None, __Factory__=BaseFactory):
        if __root__ is None:
            __root__ = []
        super().__init__(__root__=__root__)
        self.__dict__['__Factory__'] = __Factory__

    @classmethod 
    def get_system_class(cls):
        return SystemList 
    @property
    def data(self):
        return self.__root__
    def __iter__(self):
        return UserDict.__iter__(self)
    def __setitem__(self, index, value):
        if not isinstance(value, self.__Factory__):
            raise KeyError( f'item {index} is not a Factory')
    def build(self, parent=None, name="") -> "SystemList":
        system_list = SystemList( 
                [factory.build(parent, name+"["+str(i)+"]") for i, factory in enumerate(self) ]
            )
        if parent:
            system_list.__get_parent__ = weakref.ref(parent) 
        return system_list 

class BaseFactoryAttribute:
    def get_attribute_config_class(self, cls):
        field = cls.Config.__fields__[self.attr] 
        return field.get_default()

class ConfigAttribute:
    def __init__(self, attr=None):
        self.attr = attr
    def __get__(self, parent, cls=None):
        if parent is None: return self
        
        obj =  getattr( parent.__config__, self.attr)
        # this test should go away at some point 
        if isinstance(obj, BaseFactory):
            return obj._build_and_save_in_parent(parent,  self.attr)
        else:
            return obj 

    def __set__(self, parent, value):
        if getattr(parent, "_allow_config_assignment", False):
            setattr( parent.__config__, self.attr, value)
        else:
            raise ValueError(f"cannot set config attribute {self.attr!r} ")
    def __set_name__(self, parent, name):
        if self.attr is None:
            self.attr = name 

class SubsystemAttribute(BaseFactoryAttribute):
    def __init__(self, attr=None, alias=None):
        self.attr = attr
        self.alias = alias 

    def __get__(self, parent, cls=None):
        if parent is None: return self.get_attribute_config_class(cls) 

        factory = getattr( parent.__config__, self.attr)
        if factory is None:
            return None
        return factory._build_and_save_in_parent(parent, self.alias or self.attr)
    
    def __set_name__(self, parent, name):
        if self.attr is None:
            self.attr = name 


class SubsystemDictAttribute(BaseFactoryAttribute):
    def __init__(self, attr=None, alias=None):
        self.attr = attr
        self.alias = alias 

    def __get__(self, parent, cls=None):
        if parent is None:       
            return self
        factories = getattr( parent.__config__, self.attr)
        
        if isinstance(factories, FactoryDict):
            return factories._build_and_save_in_parent( parent, self.alias or self.attr)
        else:
            return FactoryDict(factories)._build_and_save_in_parent( parent, self.alias or self.attr)
    
    def __set_name__(self, parent, name):
        if self.attr is None:
            self.attr = name 


class SubsystemListAttribute(BaseFactoryAttribute):
    def __init__(self, attr=None, alias=None):
        self.attr = attr
        self.alias = alias 

    def __get__(self, parent, cls=None):
        if parent is None: return self
        factories = getattr( parent.__config__, self.attr)
        if isinstance( factories, FactoryList):
            return factories._build_and_save_in_parent( parent, self.alias or self.attr)
        else:
            return FactoryList(factories)._build_and_save_in_parent( parent, self.alias or self.attr)
            
    
    def __set_name__(self, parent, name):
        if self.attr is None:
            self.attr = name 

def _rebuild_config_class(ParentClass: "BaseSystem", Config: BaseConfig, kwargs: Dict) -> Type[BaseConfig]:
    """ Rebuild the Config class associated to a ParentClass 

    At least the Config is always inerited in order to modify it with 
    new kwargs and to mutate the weak reference to the parent class
    """
    if not issubclass(Config, BaseFactory):
        for subcl in ParentClass.__mro__[1:]:
            try:
                ParentConfigClass = getattr(subcl, "Config")
            except AttributeError:
                continue
            else:
                break 
        else:
            raise ValueError("Cannot find a Config class")
        kwargs = {**kwargs, **_class_to_model_args(Config)}
        
    else:
        ParentConfigClass = Config
        
    NewConfig =  create_model(  ParentClass.__name__+".Config",  __base__= ParentConfigClass, **kwargs)        
    return NewConfig

def _set_parent_class_reference(ParentClass: "BaseSystem", Config: BaseConfig) -> None:
    """ Set a reference in Config pointing to the ParentClass """
    Config.__parent_system_class_ref__ = weakref.ref(ParentClass)

def _create_factory_attributes(Config: BaseConfig) -> dict:
    """ Populate ParentClass with any Sub-System Configuration found in Config """
    attributes = {}
    for name, field in Config.__fields__.items():
        field_type = _get_field_type(field)

        if field_type == MemberType.FactoryDict:
            attributes[name] =  SubsystemDictAttribute(name)
            # mutate a normal dict to a Factorydict (this is safe because a copy)
            # if field.default is not None and not isinstance(  field.default, FactoryDict ):
            #     field.default = FactoryDict( field.default )

        elif field_type == MemberType.FactoryList:
            attributes[name] = SubsystemListAttribute(name)
            # if field.default is not None and not isinstance(  field.default, FactoryList ):
            #     field.default = FactoryList( list(field.default) )

        elif field_type == MemberType.Factory:
            attributes[name] = SubsystemAttribute(name)
        else:
            attributes[name] = ConfigAttribute(name)

    return attributes 


def _set_factory_attributes(ParentClass: "BaseSystem", attributes: Dict) -> None:
    """ Set a dictionary of attributes into the class """
    for name, obj in attributes.items():
        try:
            getattr( ParentClass, name)
        except AttributeError:
            setattr(ParentClass, name, obj)


def _get_extra_config_attribute(system, attr):
    """ use has __getattr__ when Config class allows extra element 

    Since we cannot know the content of the config instance we need 
    to provide a __getattr__ 
    """
    try:
        return object.__getattribute__(system, attr)
    except AttributeError:
        obj = getattr(system.__config__, attr)
        if isinstance(obj, BaseFactory):
            return obj._build_and_save_in_parent(system, attr)
        return obj



def systemclass(cls, **kwargs):
    cls.Config = _rebuild_config_class(cls, cls.Config, kwargs)
    _set_parent_class_reference( cls, cls.Config)
    _set_factory_attributes( cls, _create_factory_attributes(cls.Config) ) 

    if cls.Config.__config__.extra == Extra.allow:
        if not hasattr(cls, "__getattr__"):
            cls.__getattr__ = _get_extra_config_attribute
    return cls


class BaseSystem(ABC):
    __config__ = None  
    _allow_config_assignment = False
    __factory_classes__ = set() 

    class Config(BaseConfig):
        ...
    
    def __init_subclass__(cls, **kwargs) -> None:
        systemclass(cls, **kwargs)

    def __init__(self,* , __config__=None, __path__= None, **kwargs):
        if isinstance(__config__, dict):
            __config__ = self.Config(**__config__)

        if __config__ is None:
            __config__ = self.Config(**kwargs)
        elif kwargs:
            raise ValueError("Cannot mix __config__ argument and **kwargs")
        self.__config__ = __config__ 
        self.__path__ = __path__

    # def __getattr__(self, attr):
    #     try:
    #         return object.__getattribute__(self, attr)
    #     except AttributeError:
    #         obj = getattr(self.__config__, attr)
    #         if isinstance(obj, BaseFactory):
    #             obj.__set_name__(self, attr)
    #             return obj.__get__(self, None)
    #         return obj
   
    # def _build_all(self, depth: int=0):
    #     """ Build all subsystem located in __config__ """
    #     for name, field in self.__config__.__fields__.items():
    #         # if issubclass( field.type_, BaseFactory):
    #             # getting the attribute will build the subsystem inside self.__dict__
    #             obj = getattr(self, name)
    #             if isinstance(obj, BaseSystem) and depth:
    #                 obj._build_all(depth-1)

    def reconfigure( self, __d__: Optional[Dict[str, Any]] = None, **kwargs):
        """ Configure system """
        if __d__: 
            kwargs = dict(__d__, **kwargs)
        for key, value in kwargs.items():
             setattr(self.__config__, key, value)

    def find(self, SystemType: Type["BaseSystem"], depth: int=0)-> Iterable:
        # self._build_all()
        for attr in dir(self):
            if attr.startswith("__"): continue
            try: # durty patch to avoid side effect 
                obj = getattr(self, attr)
            except (ValueError, AttributeError, KeyError) as e:
                
                if has_factory( self.__class__, attr):
                    raise e
                else:
                    continue 
            if isinstance(obj, SystemType):
                yield obj

            if depth and _is_subsystem_iterable(obj):
                for other in obj.find(SystemType, depth-1):
                    yield other 
    
  
    def children(self, SystemType: Optional[Type["BaseSystem"]] = None):
        if SystemType is None:
            SystemType = BaseSystem
        for attr in dir(self):
            if attr.startswith("__"): continue 
            # obj = getattr(self, attr)
            try:
                obj = getattr(self, attr)
            except (ValueError, AttributeError, KeyError):
                continue 

            if isinstance(obj, SystemType):
                yield attr


    
class SystemDict(UserDict):

    def __setitem__(self, key, system):
        super().__setitem__(key, self.__parse_item__(system, key))    
            
    def find(self, SystemType: Type[BaseSystem], depth: int =0):
        for system in self.values():
            if isinstance(system, SystemType):
                yield system 
            if depth and _is_subsystem_iterable(system):
                for other in system.find( SystemType, depth -1):
                    yield other 
    
    def children(self, SystemType: Optional[Type["BaseSystem"]] = None):
        return 
        yield 
     
    def reconfigure( self, __d__: Optional[Dict[str, Any]] = None, **kwargs):
        if __d__: 
            kwargs = dict(__d__, **kwargs)
        if kwargs: raise ValueError( "SystemDict is not reconfigurable" )


    def __parse_item__(self, item, key):
        if isinstance( item, BaseFactory):
            item = self.__factory_item_builder__(item, key) 

        if not isinstance(item, (BaseSystem, SystemDict, SystemList)):
            raise KeyError(f"new item is not an iterable system")
        return item 
    
    def __get_parent__(self):
        raise ValueError("This SystemList is not attached to any parent")
    
    def __factory_item_builder__(self, factory, key):
        parent = self.__get_parent__()
        return factory.build(parent, "["+repr(key)+"]") 


class SystemList(UserList):
    def append(self, item):
        super().append(self.__parse_item__(item))
    def extend(self, items):
        super().extend( self.__parse_item__(item) for item in items)
    def insert(self, i, item):
        super().insert( i, self.__parse_item__(item, i))
        
    def __setitem__(self, index, system):
        system = self.__parse_item__(system , index)
        super().__setitem__(index, system)    
            
    def find(self, SystemType: Type[BaseSystem], depth: int =0):
        for system in self:
            if isinstance(system, SystemType):
                yield system 
            if depth and _is_subsystem_iterable(system):
                for other in system.find( SystemType, depth -1):
                    yield other 
    
    def children(self, SystemType: Optional[Type["BaseSystem"]] = None):
        return 
        yield 
     
    def reconfigure( self, __d__: Optional[Dict[str, Any]] = None, **kwargs):
        if __d__: 
            kwargs = dict(__d__, **kwargs)
        if kwargs: raise ValueError( "SystemDict is not reconfigurable" )

    def __parse_item__(self, item, index=None):
        if index is None: index = len(self)
        if isinstance( item, BaseFactory):
            item = self.__factory_item_builder__(item, index) 

        if not isinstance(item, (BaseSystem, SystemDict, SystemList)):
            raise KeyError(f"new item is not an iterable system")
        return item 
    
    def __get_parent__(self):
        raise ValueError("This SystemList is not attached to any parent")
    
    def __factory_item_builder__(self, factory, index):
        parent = self.__get_parent__()
        return factory.build(parent, "["+str(index)+"]") 
        
def _is_subsystem_iterable(system):
    return isinstance( system , (BaseSystem, SystemDict, SystemList))


def find_factories(cls,  
        SubClass=(BaseSystem, SystemDict, SystemList), 
        include:Optional[set] = None, 
        exclude:Optional[set] = None
    )-> List[Tuple[str, BaseFactory]]:
    """ find factories defined inside a system class 

    The factories are matched thanks to a Class or a tuple of Classes 
    of subsystems built by the factory
    
    Note1 find_factories is a generator
    Note2 all attribute starting with "__" are skiped 
    Note3 find_factories is not recursive

    Args:
        cls : The root class to search 
        SubClass (optional, Type, Tuple[Type]): match the System class(es)
            which shall be created to the factory  
        include (optional, set[str]): A set of str attribute to include only
        exclude (optional, set[str]): Exclude this set of attribute 

    Returns:
        generator of tuple of: 
            attr (str): attribute name 
            factory (BaseFactory): matched factories  
    """
    
    found = set()
    iterator = dir(cls) if include is None else include
    
    if exclude is None: 
        exclude = set() 
    for attr in iterator:
        if attr.startswith("__"): continue
        if attr == "Config": continue 
        if attr in exclude: continue
        
        try:
            obj = getattr( cls, attr)
        except AttributeError:
            continue 
        if not isinstance(obj, BaseFactory):
            continue
        
        try:
            System  = obj.get_system_class()
        except ValueError:
            continue

        if not issubclass(System, SubClass):
            continue 
        found.add(attr)
        yield (attr,obj) 
    
    if not issubclass(cls, BaseSystem):
       return 

    fields = cls.Config.__fields__                 
    iterator = fields if include is None else include
    for attr  in iterator:
         
        if attr in found: continue 
        if attr in exclude: continue
        try:
            field = fields[attr] 
        except KeyError:
            continue 
        
        
        try:
            obj = field.get_default()
        except (ValueError, TypeError):
            continue 
        
        field_type =  _get_field_type(field) 
        if field_type == MemberType.Other:
            continue
        

        if field_type == MemberType.FactoryList:
            if isinstance(obj, FactoryList):
                yield (attr, obj)
            else:
                yield (attr, FactoryList(obj))
        
        elif field_type == MemberType.FactoryDict:
            if isinstance(obj, FactoryDict):
                yield (attr, obj)
            else:
                yield (attr, FactoryDict(obj))
        else: 
            try:
                System  = obj.get_system_class()
            except ValueError:
                continue
           
            if not issubclass(System, SubClass):
                continue 
            
            yield (attr, obj)
    
def has_factory(cls, attr):
    try:
        factory = getattr(cls,attr)
    except AttributeError:
        try: 
            field = cls.Config.__fields__[attr]
        except KeyError:
            return False

        field_type =  _get_field_type(field)
        if field_type == MemberType.Other:
            return False 
        return True 
    
    print( factory )
    if not isinstance(factory, (BaseFactory, BaseFactoryAttribute)):
        return False
    return True
    


def factory(SystemClass):
    """ a decorator on a factory class 

    this does a few things: 
        - It implement the get_system_class method if not implemented
            by adding a weakref to the targeted SystemClass 
        - It add the factory class to the set of __factory_classes__ inside BaseSystem (for future use)
    """
    if not issubclass( SystemClass, BaseSystem):
        raise ValueError("factory(cls) expect a BaseSystem class")
    def factory_class_decorator(cls):
        try:
            cls.get_system_class()
        except (NotImplementedError, ValueError):
            cls.get_system_class = weakref.ref(SystemClass)
        SystemClass.__factory_classes__.add( cls )
        return cls 
    return factory_class_decorator


if __name__ == "__main__":
    class X(BaseSystem):
        class Config:
            x: int =0
    class X2(BaseSystem):
        class Config:
            x: int =1 
    

    class MyYoFD(FactoryDict):
        def toto(self): return  1 

    class M(BaseModel):

        # d: FactoryDictVar[str, BaseFactory] = {}
        # d2: FactoryDict[str, BaseFactory] = {}  
        d2: FactoryDict[str, X.Config]= {}  
        d3: FactoryDict = FactoryDict()
        d4 = FactoryDict() 
        d5: MyYoFD[int, X.Config] = {} 

    # print( M(  d2 = {"a": X.Config(x=1)},  d3= {}  ) )

    m =  M( d2= {'a':X2.Config()} , d4={}, d5={} )
    print( m  ) 
    print( m.d5.toto() )
    print( m.__fields__['d5'])

    class M(BaseModel):
        l: FactoryList[X.Config] = []
    M(l = [] )


