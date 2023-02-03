from enum import Enum
from typing import List, Optional, Tuple
from attr import dataclass
from pydantic.errors import PydanticErrorMixin
import yaml
from .system import BaseFactory, BaseSystem
from py_expression_eval import Parser 
from pydantic import ValidationError
import math 
import re
import os
_math_parser  = Parser()
_math_args = {k:v for k,v in math.__dict__.items() if not k.startswith("_")} 
del Parser

_factory_loockup = {}
""" Dictionary containing all target """



def split_factory_definition(name):
    # "Elt:Device/Motor"
    # "Elt:Motor"
    # "Motor"
    # "Device/Motor"
    left, _, right = name.partition(":")
    if right:
        namespace, kind_name = left, right
    else:
        namespace, kind_name = None, left 

    left, _,  right = kind_name.partition("/")
    if right:
        kind, name = left, right 
    else:
        kind, name = None, left 
    return namespace, kind, name


def register_factory(name, cls=None, namespace=None, kind=None):
    """ Record a factory with its name 
    
    Usage:
        @register_factory(name) 
        class MyFactory(BaseFactory):
            ...

        Or 

        register_factory(name, MyFactory)

    """
    if isinstance(name, type) and cls is None:
        name, cls = name.__name__, name
       
    
    rns, rkind, rname = split_factory_definition(name)
    if rns is not None:
        if namespace:
            raise ValueError("namespace is defined twice, from name and keyword")
        else:
            namespace = rns 
            name = rname 
    if rkind is not None:
        if kind:
            raise ValueError("kind is defined twice, from name and keyword")
        else:
            kind = rkind
            name = rname
     

    def factory_recorder(icls):
        if issubclass(icls, BaseSystem):
            fcls = icls.Config
        else:
            fcls = icls 
        if not hasattr(fcls, "build"):
            raise ValueError("Factory must have a `build` method")
        
        _factory_loockup[ (None,None,name) ] = fcls
        _factory_loockup[ (None,kind,name) ] = fcls 
        _factory_loockup[ (namespace, kind, name) ] = fcls
        _factory_loockup[ (namespace, None, name) ] = fcls

        return icls
    
    if cls:
        return factory_recorder(cls)
    else:
        return factory_recorder
        

def get_factory_class(name, namespace=None, kind=None) -> BaseFactory:
       
    rns, rkind, name = split_factory_definition(name)
    namespace = namespace or rns 
    kind = kind or rkind

    try:
        return _factory_loockup[(namespace,kind,name)]
    except KeyError:
        raise ValueError(f"Unknown factory {name!r} kind {kind!r} in namespace {namespace!r}")

def get_system_class(name, namespace=None, kind=None):
    Factory = get_factory_class(name, namespace=namespace, kind=kind)
    System = Factory.get_system_class()
    if System is None:
        raise ValueError(f"Factory {name} exists but is not associated to any System")
    return System 


def iter_factory(kind: Optional[str]=None, namespace: Optional[str]=None):
    for (ns,k,n), Factory in _factory_loockup.items():
        if ns==namespace and k==kind:
            yield n, Factory

def iter_system_class(kind: Optional[str]=None, namespace: Optional[str]=None):
    for n, Factory in iter_factory(kind=kind, namespace=namespace):
        try:
            System = Factory.get_system_class()
        except ValueError:
            pass
        else:
            yield n, System


@dataclass
class SystemIo:
    default_path: str = "." # default path definition if path environment var not found     
    path_env_name: str = "SYSTEMYPATH" # name of the environmnet variable defining path 

    def get_path_list(self) -> List[str]:
        return os.environ.get(self.path_env_name, self.default_path).split(':')

    def find(self, file_name: str):
        """ find a config file and return its absolute path 
        
        Args:
            file_name (str): config file name. Should be inside one of the path defined by the $CFGPATH 
        """
        path_list = self.get_path_list()
        
        for directory in path_list[::-1]:
            path = os.path.join(directory, file_name)
            if os.path.exists(path):
                return  path
        raise ValueError('coud not find config file %r in any of %s'%(file_name, path_list))

    def resolve(self, path: str)-> Tuple[str, Tuple]:
        """ Return an absolute file name path and a tuple internal file path 

        "some_file.yaml(a.b.c)" -> "/abs/path/to/some_file.yaml", ("a","b","c")
        
        The arg (the tuple) define where is the target in the file
        """
        file, path = parse_file_name(path)
        return self.find(file), path 




class YamlTags(str, Enum):
    FACTORY = "!factory:"
    MATH = "!math"
    INCLUDE = "!include:"
    
class SystemLoader(yaml.CLoader):
    io = SystemIo()

def add_multi_constructor(tag, constructor):
    return yaml.add_multi_constructor( tag, constructor, SystemLoader)

def add_constructor(tag, constructor):
    return yaml.add_constructor( tag, constructor, SystemLoader)

def _get_factory_from_tag_suffix(tag_suffix):
    if not tag_suffix:
        raise ValueError("Missing factory name for tag {YamlTags.FACTORY}")
    else:
        return get_factory_class(tag_suffix)

def factory_constructor(loader, tag_suffix, node):
    
    Factory = _get_factory_from_tag_suffix(tag_suffix)
    if isinstance(node, yaml.MappingNode):
        raw = loader.construct_mapping(node, deep=True)
    elif isinstance( node, yaml.ScalarNode):
        raw = loader.construct_scalar(node) 
    elif isinstance( node, yaml.SequenceNode):
        raw = loader.construct_sequence(node, deep=True)
    else:
        raise ValueError("object flag expecting a map")
    return validate_factory(Factory, raw)
    

add_multi_constructor( YamlTags.FACTORY, factory_constructor)


def math_constructor(loader, node):
    return _math_parser.parse(loader.construct_scalar(node)).evaluate(_math_args)
add_constructor( YamlTags.MATH, math_constructor)

def validate_factory(Factory, raw):
    errors = []
    for validator in Factory.__get_validators__():
        
        try:
            value = validator( raw )
        except (ValueError, KeyError, TypeError, ValidationError ) as e:
            errors.append(e)
        else:
            return value 
    
    raise ValidationError(errors, Factory) 


def include_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.MappingNode):
        data = loader.construct_mapping(node)
    elif isinstance(node, yaml.ScalarNode):
        if node.value:
            raise ValueError("!include tag is out of context")
        else:
            data = {}
            
    io = loader.io 
    
    file_name, path = io.resolve(tag_suffix.strip())
    
    with open(file_name, "r") as f :
        src = yaml.load(f.read(), loader.__class__)
        src = goto_target(src, path)

    if not isinstance( src, BaseFactory):
        raise ValueError("Include target must be factory")
    
    for k,v in data.items():
        setattr( src, k, v)
    return src 

add_multi_constructor( YamlTags.INCLUDE, include_constructor)



_re_path_pattern_brackets = re.compile( '^([^\\(]+)\\(([^\\)]*)\\)$' )
def parse_file_name(file_name: str):
    """ split a file name into real file and path tuple"""
    g = _re_path_pattern_brackets.search(file_name)
    if not g:
        return file_name, None
        
    file, path = g[1], g[2]     
    return file.strip(' '), tuple( p for p in path.strip(' ').split('.') if p)


def goto_target(src, path):
    if path is None: return src 
    for item in path:
        if isinstance(src, BaseFactory):
            src = getattr(src,item)
        else:
            src = src[item]
    return src

