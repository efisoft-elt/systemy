from pydantic.main import BaseModel
import pytest
from systemy.loaders import register_factory

from systemy.model_instance import InstanceOf
from systemy.system import BaseFactory

class MyBase(BaseFactory):
    pass 

@register_factory
class F(MyBase):
    num: int = 10
    class Config:
        extra = "forbid"
    def build(self, parent=None, name=None):
        return self.num  

@register_factory
class F2(MyBase):
    num: int = 10
    scale: float 
    def build(self, parent=None, name=None):
        return self.num*self.scale  

@register_factory
class F3(MyBase):
    num: int = 10
    scale: float 
    offset: float = 0 
    def build(self, parent=None, name=None):
        return self.num*self.scale  

@register_factory
class NotAMyBase(BaseFactory):
    pass


class M(BaseModel):
    f : InstanceOf[MyBase] 


def test_instance_of_from_factory():

    m = M(f= F(num=9) )
    assert m.f.build() == 9

def test_instance_of_from_dict():

    m = M(f=  {'num':9} )
    assert m.f.build() == 9

    m = M(f=  {'num':9, 'scale':9} )
    assert m.f.build() == (9*9)
    
    m = M( f={'num':9, 'scale':9})
    assert isinstance( m.f, F3) 
    
    m = M( f={'num':9, 'scale':9, '__factory__':'F2'})
    assert isinstance( m.f, F2) 

def test_validation_error_when_bad_factory():
    
    with pytest.raises(ValueError):
        M( f={"__factory__":"NotAMyBase"})
