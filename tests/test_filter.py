from systemy.filter import FilterFactory
from systemy.system import BaseSystem, FactoryList


def test_filter_base():
    
    class Child(BaseSystem):
        class Config:
            name: str = None 
    
    class S(BaseSystem):
        c1 = Child.Config(name="c1")
        c2 = Child.Config(name="c2")
        
        childs  = FilterFactory()

    s = S()
    assert len(s.childs) == 2

    class S(BaseSystem):
        c1 = Child.Config(name="c1")
        c2 = Child.Config(name="c2")
        l = FactoryList( [Child.Config( name="l1")] )
        childs  = FilterFactory(depth=-1, Base=Child)

    s = S()
    assert len(set(s.find(Child, -1))) == 3
    assert len(s.childs) == 3
test_filter_base()
