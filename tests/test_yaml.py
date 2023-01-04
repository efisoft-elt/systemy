from systemy.loaders import SystemLoader, get_factory_class, get_system_class, register_factory, split_factory_definition
from systemy.system import BaseFactory, BaseSystem
import yaml
import pytest 

test1 = """!factory:House
width: 10
"""

test2 = """!factory:House
bedroom: !factory:Room
   width: 3
   height: 4
"""


test3 = """!factory:House
bedroom: !factory:Any
   type: Room 
   width: 5
   height: !math 3+4
   misc: !math sin(pi/2.0)
"""

test_file = """!factory:Room
width: 2 
height: 3 
"""

test_file2 = """!factory:House
big_room:
    parent_room: !factory:Room
        width: 2 
        height: 3 
"""


test4 = """!factory:Thing/House
bedroom: !include:/tmp/test_system.yaml
"""
test5 = """!factory:Test:House
bedroom: !include:/tmp/test_system.yaml
    width: 6
"""
test6 = """!factory:Test:Thing/House
bedroom: !include:/tmp/test_system.yaml(big_room.parent_room)
    width: 7
"""


@register_factory("Test:Thing/House")
class House(BaseSystem):
    class Config:
        width: float = 99
        height: float = 99
        class Config:
            extra = "allow"

@register_factory
class Room(BaseSystem):
    class Config:
        width: float = 99
        height: float = 99
        misc: float = 0.0

@register_factory("Any")
class Any(BaseFactory): 
    type: str
    class Config:
        extra = "allow"

    def build(self, parent=None, name=""):
        F = get_factory_class(self.type)
        return F.parse_obj( self.dict(exclude=set(['type'])) ).build( parent, name) 


def test_factory_loader():
    f = yaml.load( test1, SystemLoader) 
    assert isinstance( f, House.Config)
    assert f.width == 10
    assert f.height == 99
    assert f.build().width == 10 

    f = yaml.load( test2, SystemLoader)
    assert f.bedroom.width == 3 
    assert f.build().bedroom.width == 3
    
    f = yaml.load( test3, SystemLoader)
    s = f.build() 
    assert f.bedroom.width == 5
    assert s.bedroom.width == 5
    assert s.bedroom.height == 7
    assert s.bedroom.misc == 1.0
    # assert isinstance( s.bedroom, Room) 



def test_include_loader():
    with open("/tmp/test_system.yaml", "w") as g:
        g.write(test_file)
    f = yaml.load( test4, SystemLoader)
    assert f.bedroom.width == 2

    f = yaml.load( test5, SystemLoader)
    assert f.bedroom.width == 6
    
    with open("/tmp/test_system.yaml", "w") as g:
        g.write(test_file2)
    f = yaml.load( test6, SystemLoader)
    assert f.bedroom.width == 7



def test_factory_name_structure():

    assert split_factory_definition("ns:kind/name") == ("ns","kind", "name")
   
    assert split_factory_definition("kind/name") == (None,"kind", "name")
    assert split_factory_definition("name") == (None,None, "name")
    assert split_factory_definition("ns:name") == ("ns", None, "name")



def test_get_system_class():
    assert get_system_class("House") is House

test_factory_name_structure()

# test_factory_loader() 
# test_include_loader()
