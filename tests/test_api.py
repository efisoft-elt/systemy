from typing import Dict, List, Optional, Union
import pytest

from systemy.system import BaseFactory, BaseSystem, BaseConfig, FactoryDict, FactoryList, SystemDict, SystemList, factory , find_factories, get_factory,  has_factory

def test_config_class_creation():
    
    BaseConfig()

    with pytest.raises( ValueError):
        BaseConfig().build()

def test_subclass_system():

    class Room(BaseSystem):
        class Config:
            width: float = 1.0
            height: float = 1.0

    class House(BaseSystem):
        class Config:
             bedroom = Room.Config(width=10, height=12.0)
        
        closet = Room.Config( width=3, height=1)
    house = House(bedroom={"width":13})
    assert house.__config__.bedroom.width == 13
    assert house.__config__.bedroom.height == 1.0
    print( house.bedroom.__config__,  house.__config__.bedroom) 
    assert house.bedroom.width == 13
    assert house.bedroom.height == 1.0
    assert isinstance(house.bedroom, Room)
    assert house.closet.width == 3


def test_find():

    class Window(BaseSystem):
        pass
    
    class Room(BaseSystem):
        class Config:
            width: float = 1.0
            height: float = 1.0
            window = Window.Config() 

    class House(BaseSystem):
        class Config:
             bedroom = Room.Config(width=10, height=12.0)
             window = Window.Config()
        garage = Room.Config()
    house = House()
    # print( list(house.find(Room)))
    print( list(house.find(BaseSystem, -1)))
    assert len( list(house.find(Room))) == 2
    assert len( list(house.find(BaseSystem))) == 3
    assert len( list(house.find(BaseSystem,-1))) == 5
    assert len( list(house.find(Window,-1))) == 3
    
    assert house.bedroom.__path__ == "bedroom"
    assert house.bedroom.window.__path__ == "bedroom.window"
    assert isinstance(house.garage, BaseSystem)
    assert house.garage.__path__ == "garage"

def test_find_for_extras():
    class Room(BaseSystem):
        class Config:
            width: float = 1.0
            height: float = 1.0
    class House(BaseSystem, extra="allow"):
        ...

    house = House( 
        bedroom = Room.Config(width=10, height=10), 
        toilet = Room.Config( width=2.0, height=1.0)
    )
    assert len(list(house.find(Room))) == 2 



def test_factory_dict():
    class Room(BaseSystem):
        class Config:
            width: float = 1.0
            height: float = 1.0

    class House(BaseSystem):
        class Config:
            # rooms : FactoryDict[str, BaseConfig]  = FactoryDict( {'bedroom': Room.Config(width=9), 'livingroom': Room.Config()} )
            rooms : FactoryDict[str, Room.Config]  = {'bedroom': Room.Config(width=9),  'livingroom': Room.Config()}
    house = House()
    rs = house.rooms
    
    assert isinstance( rs['bedroom'], BaseSystem)
    assert house.rooms['bedroom'].width == 9
    assert len( list(house.find( Room, 1))) == 2
    
    assert house.rooms['bedroom'].__path__ == "rooms['bedroom']"
    

    # with pytest.raises( ValueError):
    #     House( rooms={'bedroom':3})
    # house2 = House( rooms={'bedroom':BaseSystem.Config()})
     
def test_factory_list():
    
    class Room(BaseSystem):
        class Config:
            width: float = 1.0
            height: float = 1.0

    class House(BaseSystem):
        class Config:
            rooms: FactoryList[Room.Config] = [Room.Config(), Room.Config(width=9)]
        
        garages = FactoryList([Room.Config()])

    house = House()
    house.rooms
    assert house.rooms[1].width == 9
    assert len(house.rooms) == 2 
    assert house.rooms[1].__path__ == "rooms[1]"
    assert isinstance( house.garages[0], BaseSystem)


def test_set_config_attribute_must_be_value_error():

    class S(BaseSystem):
        class Config:
            a: int  = 0
    s = S()
    with pytest.raises(ValueError):
        s.a = 2
    
    class S(BaseSystem):
        _allow_config_assignment = True
        class Config:
            a: int  = 0
    s = S()
    s.a = 2
    assert s.a == 2


def test_reconfigure():
    class S(BaseSystem):
        class Config:
            a: int  = 0
    s = S()
    s.reconfigure( a=10)
    assert s.a == 10

def test_optional_subsystem():

    class S1(BaseSystem):
        ...

    class S0(BaseSystem):
        class Config:
            s: Optional[S1.Config] = None

    s0 = S0()
    assert s0.s is None

def test_factory_union():

    
    class S1(BaseSystem):
        class Config:
            x: int  = 1
    class S2(BaseSystem):
        ...

    class S0(BaseSystem):
        class Config:
            s: Union[S1.Config, S2.Config] = S1.Config()
    
    s0 = S0( s=S2.Config() )
    assert isinstance( s0.s, BaseSystem) 



def test_children_iterator():
    
    class S1(BaseSystem):
        ...
    class S2(BaseSystem):
        ...
    
    class S0(BaseSystem):
        class Config:
            s1= S1.Config()
            s2= S2.Config()
    
    s = S0()
    assert list( s.children()) == ["s1", "s2"] 
    
    class S0(BaseSystem):
            s1= S1.Config()
            s2= S2.Config()
    s = S0() 
    assert list( s.children()) == ["s1", "s2"] 
    
    assert list( s.children(S1)) == ["s1"] 
    
    assert list( s.children( (S1,S2) )) == ["s1", "s2"] 
    

def test_append_factory_in_list():
    class S(BaseSystem):
        pass 

    class SS(BaseSystem):
        class Config:
            l2: FactoryList[S.Config] = []
            l3: FactoryList[S.Config] = FactoryList()

        l = FactoryList()

    ss = SS()
    ss.l.append( S.Config() )


    # assert isinstance( ss.l, BaseSystem)
    assert isinstance( ss.l, SystemList)
    assert isinstance( ss.l[0], S)
    ss.l.extend( [S.Config(), S.Config()])
    assert isinstance( ss.l[-1], S)
    ss.l.insert(-1, S.Config())
    assert isinstance( ss.l[0], S)
    
    # assert isinstance( ss.l2, BaseSystem)
    assert len( list(find_factories(SS, (BaseSystem, SystemList)))) == 3
    
    assert list(ss.l.children( BaseSystem)) == []


def test_append_factory_in_dict():
    class S(BaseSystem):
        pass 

    class SS(BaseSystem):
        class Config:
            d: FactoryDict[str, S.Config] = {}
            
    ss = SS()
    ss.d["one"] = S.Config() 
    assert isinstance( ss.d["one"], S)
    ss.d.update( two = S.Config() )
    assert isinstance( ss.d["two"], S)  


def test_find_factories():
    class B(BaseSystem):
        pass 
    class A(BaseSystem):
        f1 = B.Config() 
        f2 = B.Config()
    assert len(list(find_factories(A, (BaseSystem, SystemList)))) == 2
    
    class A(BaseSystem):
        f1 = B.Config() 
        l = FactoryList( [B.Config()] )

    assert len(list(find_factories(A, (BaseSystem, SystemList)))) == 2
    class A(BaseSystem):
        f1 = B.Config() 
        l = FactoryList( [B.Config()] )
        d = FactoryDict( {"b":B.Config()} )

    assert len(list(find_factories(A, (BaseSystem, SystemList)))) == 2
    assert len(list(find_factories(A, (B, SystemList, SystemDict)))) == 3

def test_find_factories_in_config():
    class B(BaseSystem):
        pass 
    class A(BaseSystem):
        class Config:
            f1 = B.Config() 
            f2 = B.Config()
    assert len(list(find_factories(A, (BaseSystem, SystemList)))) == 2
    
    class A(BaseSystem):
        class Config:
            f1 = B.Config() 
            l = FactoryList( [B.Config()] )

    assert len(list(find_factories(A, (BaseSystem, SystemList)))) == 2
    class A(BaseSystem):
        class Config:
            f1 = B.Config() 
            l = FactoryList( [B.Config()] )
            d = FactoryDict( {"b":B.Config()} )

    assert len(list(find_factories(A, (BaseSystem, SystemList)))) == 2
    assert len(list(find_factories(A, (B, SystemList, SystemDict)))) == 3
    # with a mix
    MyList = FactoryList[B.Config]
    class A(BaseSystem):
        l1 = FactoryList( [B.Config()] )
        f1 = B.Config() 
        class Config:
            f2 = B.Config() 
            l2 = FactoryList( [B.Config()] )
            l3 : MyList = [] # defult [] sould be mutated 
            d = FactoryDict( {"b":B.Config()} )
            f3: Optional[B.Config] = None
    assert len(list(find_factories(A, (BaseSystem, SystemList)))) == 5
    assert len(list(find_factories(A, (B, SystemList, SystemDict)))) == 6




def test_has_factory():
    class X(BaseSystem):
        pass 

    class A(BaseSystem):
        class Config: 
            f1 = X.Config()
            f2: FactoryList[X.Config] = [] 
        f3 = X.Config()
        f4 = FactoryList()
    
    assert has_factory(A, "f1")
    assert has_factory(A, "f2")
    assert has_factory(A, "f3")
    assert has_factory(A, "f4")


def test_factory_decorator():
    
    class A(BaseSystem):
        class Config:
            num: int = 0

    @factory(A)
    class F(BaseFactory):
        def build(self, p,n):
            return A(num=9)

    assert F.get_system_class() is A
    assert F in A.__factory_classes__


def test_mutation_of_list_and_dict_default():
    class X(BaseSystem):
        pass 

    class A(BaseSystem):
        class Config:
            l: FactoryList[X.Config] = []
            d: FactoryDict[str, X.Config] = {}

    assert isinstance( A.Config.__fields__["l"].get_default(), FactoryList)
    assert isinstance( A.Config.__fields__["d"].get_default(), FactoryDict)

def test_factory_list_as_factory_list():
    class X(BaseSystem):
        pass 

    class A(BaseSystem):
        l: FactoryList = FactoryList()
    assert A().l == []
# test_append_factory_in_dict()
# test_factory_list()
# test_find()
# # test_subclass_system()


def test_config_assignment():
    class S(BaseSystem):
        class Config:
            x = 1.0 
    
    s = S() 
    assert s.x == 1.0 
    with pytest.raises( ValueError):
        s.x = 10.0 

    class S(BaseSystem, allow_config_assignment=True):
        class Config:
            x = 1.0 
    
    s = S() 
    assert s.x == 1.0 
    s.x = 10.0 
    assert s.x == 10.0


def test_system_composition():
    class A(BaseSystem):
        class Config:
            x: int = 1  
    class B(BaseSystem):
        class Config:
            y: int = 2
    class C(A, B):
        class Config:
            z = 9
    c = C(z=9.1) 
    assert c.x == 1 
    assert c.y == 2  
    assert c.z == 9

def test_redefining_config_breaks_mro():
    class A(BaseSystem):
        class Config:
            x: int = 1  
    class B(BaseSystem):
        class Config:
            y: int = 2
    class C(A, B):
        class Config(BaseSystem.Config):
            z = 9
    c = C()
    with pytest.raises( AttributeError) :
        c.x
    assert c.z == 9 

# test_system_composition()



def test_get_factory():
    class A(BaseSystem):
        class Config:
            x: int = 1  
    class B(BaseSystem):
        class Config:
            y: int = 2
    
    class C(BaseSystem):
        a = A.Config()
        b = B.Config()
        d = FactoryDict( {} )
    c = C()
    assert get_factory(c, "a") == C.a
    assert get_factory(c, "d") == C.d
    
    # test in config and extra 
    class C(BaseSystem, extra="allow"):
        class Config:
            a = A.Config()
            b = B.Config()
            d = FactoryDict( {} )
    c = C( aa=A.Config(), dd=FactoryDict( {} ), ll=FactoryList( [] ) )
    assert get_factory(c, "a") == C.a
    assert get_factory(c, "d") == C.d
    assert isinstance( get_factory(c, "aa"), A.Config)   
    assert isinstance( get_factory(c, "dd"), FactoryDict) 
    assert isinstance( get_factory(c, "ll"), FactoryList) 
    
    



if __name__=="__main__":
    pass
    # from pydevmgr_elt import Motor 
    # print( "All good")
    
    # class X(BaseSystem):
    #     pass 
    # class F(BaseFactory):
    #     s = X.Config()
    #     l : FactoryList[X.Config] = []
    #     d : FactoryDict = {}
    # # print(F.__system_factories__)
    # print( F.__system_factories__['l'].field.default)
