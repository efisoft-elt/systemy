from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pydantic import create_model, Field, BaseModel
import weakref 
from typing import Any, Dict, Generic, Iterable, List, Optional, Tuple, Type, TypeVar, Union, get_type_hints
from collections import UserDict, UserList

from pydantic import Extra,  PrivateAttr
from pydantic.fields import ModelField

from systemy.pypath import PyPath

INIT_VALUE_KEYWORD = "__setup"

def get_model_fields(model):
    return model.__fields__ 
def get_model_config(model):
    return model.__config__ 
def get_factory_fields(model):
    return model.__system_factories__ 


@dataclass
class FactoryField:
    """ Old information on factories as found in BaseModel class """
    type_: Type["BaseFactory"]
    field: ModelField
    def _fix_field_default(self):
        default = self.field.get_default()
        # If FactoryList and default is a list -> Mutate the default 
        # samething for FactoryDict 
        if issubclass( self.field.type_, FactoryList) and not isinstance( default, FactoryList):
            self.field.default = self.field.type_(default)
        elif  issubclass( self.field.type_, FactoryDict) and not isinstance( default, FactoryDict):
            self.field.default = self.field.type_(default)

    def get_default(self):
        return self.field.get_default()


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
        validate_assignment = True 
    
    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        try:
            FactoryList
        except NameError:
            cls.__system_factories__ = {}
            return 
        
        factories = {}
        for attr, field in get_model_fields(cls).items():
            if isinstance( field.type_, type) and issubclass( field.type_, BaseFactory):
                factory_field = FactoryField(field.type_, field)
                # Warning, this can modify the field.default property 
                factory_field._fix_field_default()
                factories[attr] = factory_field  
        cls.__system_factories__ = factories 
    
    def __init__(self, *args, **kwargs):
        initvalues  = kwargs.pop(INIT_VALUE_KEYWORD, None) 
        super().__init__(*args, **kwargs)
        if initvalues: 
            for p, v in initvalues.items():
                p = PyPath(p) 
                p.set_value( self, v)


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
        # if not issubclass( Factory, BaseFactory):
        #     raise ValueError( "expecting a subclass of BaseFactory for FactoryList" )
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
        self.__root__[key] = value 
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
        # if not issubclass( Factory, BaseFactory):
            # raise ValueError( "expecting a subclass of BaseFactory for FactoryList" )
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
        self.__root__.__setitem__(index, value)
    def build(self, parent=None, name="") -> "SystemList":
        system_list = SystemList( 
                [factory.build(parent, name+"["+str(i)+"]") for i, factory in enumerate(self) ]
            )
        if parent:
            system_list.__get_parent__ = weakref.ref(parent) 
        return system_list 


class ConfigParameterAttribute:
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

class FactoryAttribute:
    """ Hold a factory_field description and an attribute name 
    
    The factory is building the system and saving it to the parent object 
    Normaly, the FactoryAttribute is called only ones
    """
    def __init__(self,  attr=None, alias=None):
        self.attr = attr
        self.alias = alias 
    def __get__(self, parent, cls=None):
        if parent is None:
            return cls.Config.__system_factories__[self.attr].get_default()

        factory = getattr( parent.__config__, self.attr)
        if factory is None: # this should only append when a factory dict is optional 
            return None 
        return factory._build_and_save_in_parent(parent, self.alias or self.attr)
    
    def __set_name__(self, parent, name):
        if self.attr is None:
            self.attr = name 




def _set_parent_class_weak_reference(ParentClass: "BaseSystem", Config: BaseConfig) -> None:
    """ Set a reference in Config pointing to the ParentClass """
    Config.__parent_system_class_ref__ = weakref.ref(ParentClass)


_AttributeDict = Dict[str,Union[FactoryAttribute, ConfigParameterAttribute]] 
def _create_factory_attributes(Config: BaseConfig) ->_AttributeDict:
    """ Populate ParentClass with any Sub-System Configuration found in Config """
    attributes = {}
    for name in get_model_fields(Config):
        if name in Config.__system_factories__:
             attributes[name] = FactoryAttribute(name)
        else:
            attributes[name] = ConfigParameterAttribute(name)
    return attributes 


def _set_factory_attributes(ParentClass: "BaseSystem", attributes: _AttributeDict) -> None:
    """ Set a dictionary of attributes into the class """
    for name, obj in attributes.items():
        # priority is on attribute defined inside the System  
        # do not overwrite them if exists 
        try:
            getattr( ParentClass, name)
        except AttributeError:
            setattr(ParentClass, name, obj)


def _collect_mro_config(mro):
    for cls in mro:
        try:
            Config = cls.Config 
        except AttributeError:
            pass
        else:
            if isinstance(Config, type)  and issubclass(Config, BaseConfig):
                yield Config 

class SystemMeta(ABCMeta):
    def __new__(cls, name, mro, kwargs, **model_config):
        ParentConfigClass = tuple(_collect_mro_config(mro))
        
        config_kwargs = {}
        
        allow_config_assignment = model_config.pop("allow_config_assignment", None)
        config_doc = None
        try:
            Config = kwargs["Config"]
        except KeyError:
            pass 
        else:
            if isinstance(Config, type) and  issubclass( Config, BaseConfig):
                ParentConfigClass = (Config,)
            else:
                if not isinstance(Config, type):
                    raise ValueError( f"Config must be a class got a {type(Config)}")
                config_kwargs =  _class_to_model_args(Config)
            
            config_doc = Config.__doc__

        if model_config:
            if "Config" in config_kwargs: 
                 raise TypeError("Specifying config in two places is ambiguous, use either Config attribute or class kwargs")
            config_kwargs["Config"] = type("Config", tuple(), model_config)
        
        if not ParentConfigClass:
            ParentConfigClass = BaseConfig
        
        NewConfig = create_model( name+"Config", __base__=ParentConfigClass, **config_kwargs)
        if config_doc is not None:
            NewConfig.__doc__ = config_doc

        kwargs["Config"] = NewConfig
        System = ABCMeta.__new__(cls,  name, mro, kwargs)
        
        _set_parent_class_weak_reference( System, System.Config)
        _set_factory_attributes( System, _create_factory_attributes(System.Config) )
        if allow_config_assignment is not None:
            System._allow_config_assignment = allow_config_assignment

        return System 


class BaseSystem(metaclass=SystemMeta):
    __config__ = None  
    _allow_config_assignment = False
    __factory_classes__ = set() 

    class Config(BaseConfig):
        ...
    
    def __init__(self,* , __config__=None, __path__= None, **kwargs):
        if isinstance(__config__, dict):
            __config__ = self.Config(**__config__)

        if __config__ is None:
            __config__ = self.Config(**kwargs)
        elif kwargs:
            raise ValueError("Cannot mix __config__ argument and **kwargs")
        self.__config__ = __config__ 
        self.__path__ = __path__
    
    def __getattr__(self, attr):
        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            # should happen only when extra attributes are allowd in __config__
            # All other attribute defined in model are capture in ConfigParameterAttribute 
            obj = getattr(self.__config__, attr)
            if isinstance(obj, BaseFactory):
                return obj._build_and_save_in_parent(self, attr)
            return obj
    
    def __dir__(self):
        lst = object.__dir__(self)
        if get_model_config(self.__config__).extra == "allow":
            for attr in self.__config__.__dict__:
                if not attr in lst:
                    lst.append(attr)
        return lst             
    

    def reconfigure( self, __d__: Optional[Dict[str, Any]] = None, **kwargs):
        """ Configure system """
        if __d__: 
            kwargs = dict(__d__, **kwargs)
        for key, value in kwargs.items():
             setattr(self.__config__, key, value)

    
    def find(self, SystemType: Type["BaseSystem"], depth: int=0, exclude_factories: List = [])-> Iterable:
        
        for attr in dir(self):
            if attr.startswith("__"): continue

            try:
                factory = get_factory(  self, attr)
            except ValueError:
                # would like to just skeep if no factory found but 
                # they are still some rare case where factory is hidden 
                # continue
                factory = None
            
            if factory and factory in exclude_factories:
                continue 
            
            try:
                obj = getattr(self, attr)
            except (ValueError, AttributeError, KeyError) as e:
                if factory:
                    raise e
                else:
                    continue 
            if isinstance(obj, SystemType):
                yield obj

            if depth and _is_subsystem_iterable(obj):
                for other in obj.find( SystemType, depth-1, exclude_factories):
                    yield other 

   


    def children(self, SystemType: Optional[Type["BaseSystem"]] = None):
        if SystemType is None:
            SystemType = BaseSystem
        for attr in dir(self):
            if attr.startswith("__"): continue 
            # obj = getattr(self, attr)
            try:
                obj = getattr(self, attr)
            except (ValueError, AttributeError, KeyError) as e:
                if has_factory( self.__class__, attr): # we care -> problem when builting the system 
                    raise e
                else:
                    continue  # we do not care, this is not a system 
            if isinstance(obj, SystemType):
                yield attr

    
class SystemDict(UserDict):

    def __setitem__(self, key, system):
        super().__setitem__(key, self.__parse_item__(system, key))    
            
    def find(self, SystemType: Type[BaseSystem], depth: int =0, exclude_factories: List = []):
        for system in self.values():
            if isinstance(system, SystemType):
                yield system 
            if depth and _is_subsystem_iterable(system):
                for other in system.find( SystemType, depth -1):
                    yield other 
    
    def children(self, SystemType: Optional[Type["BaseSystem"]] = None):
        """ This return an empty iterator, SystemDict children are accessed true .keys() """
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
            
    def find(self, SystemType: Type[BaseSystem], depth: int =0, exclude_factories: List = []):
        for system in self:
            if isinstance(system, SystemType):
                yield system 
            if depth and _is_subsystem_iterable(system):
                for other in system.find( SystemType, depth -1):
                    yield other 
    
    def children(self, SystemType: Optional[Type["BaseSystem"]] = None):
        """ This return an empty iterator, SystemList children are accessed iterating on it """
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
        
        yield (attr,obj) 
        

def has_factory(cls: Type[BaseSystem], attr: str)-> bool:
    try:
        factory = getattr(cls,attr)
    except AttributeError:
        return False 
    return isinstance( factory, BaseFactory)

def get_factory(obj: BaseSystem, attr: str):
    try:
        factory = getattr(obj.__class__, attr)
    except AttributeError:
        if hasattr( obj, "__config__"):
            return _get_config_factory( obj.__config__, attr)
        else:
            ValueError( f"attribute {attr} is not a factory" )
    else:
        if not isinstance( factory, BaseFactory):
            raise ValueError( f"attribute {attr} is not a factory" )
        return factory 

def _get_config_factory(config, attr ):
    try:
        factory = getattr(config, attr)
    except AttributeError:
        raise ValueError("attribute {attr} is not a factory")
    else:
        if not isinstance( factory, BaseFactory):
            raise ValueError( f"attribute {attr} is not a factory" )
        return factory 




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
    from abc import ABC  

    class Toto(ABC):
        pass

    class X(BaseSystem):
        class Config:
            x: int =0
    class Y(BaseSystem):
        class Config:
            y: int =1

    class XY(X,Y, Toto):
        pass
    
    class X2(X):
        pass 
    assert isinstance( X2.Config(), X.Config)

