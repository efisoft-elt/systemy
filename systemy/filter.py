from typing import Callable, Iterable, Set, Type

from pydantic  import Field
from .system import BaseFactory, BaseSystem, SystemList
from .autodoc import autodoc 

@autodoc
class FilterFactory(BaseFactory):
    """ A factory building a SystemList containing all sub-system matching a filter

    __autodoc__
    """
    filter: Callable = Field (lambda x:True, 
            description="Filter function f(s)->bool where s is a system"
            )
    Base: Type = Field(BaseSystem, 
            description="Base sub-System type to filter"
            ) 
    depth: int = Field(-1, 
            description="Depth of the filter -1 is infinit depth"
        )
    
    @classmethod 
    def get_system_class(cls):
        return SystemList
    
    def build(self, parent, name)->SystemList:
        lst = []
        for obj in parent.find(self.Base, self.depth, exclude_factories=[self] ):
            if self.filter(obj):
                lst.append( obj )
        return self.get_system_class()( lst )


