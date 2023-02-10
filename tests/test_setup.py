import yaml
from systemy.system import BaseFactory, FactoryDict, FactoryList

class BF(BaseFactory):
    z: int = 0
    def build(self, parent=None, name=None):
        return None 

class F0(BF):
    class F1(BF):
        x: int = 0
        l: FactoryList[BF] = FactoryList( [BF(z=1), BF(z=2), BF(z=3)])
        d: FactoryDict[str, BF] = FactoryDict( {'a': BF(z=1), 'b':BF(z=2)})
        class F2(BF):
            x: int = 0
        f2 = F2()
    f1 = F1()



def test_setup_initialisation():
    setup = {
        'f1.f2.x' : 10, 
        'f1.x' : 8, 
    }
    f = F0( __setup__=setup)
    assert f.f1.f2.x == 10 
    assert f.f1.x == 8
    assert f.f1.l[1].z == 2 
    assert f.f1.d['b'].z == 2 
    setup = {
        'f1.l[1].z' : 20,
        'f1.d["b"].z': 20 
    }
    f = F0( __setup__=setup)
    assert f.f1.l[1].z == 20 
    assert f.f1.d['b'].z == 20



def test_setup_initialisation_from_yaml():
    payload = """
    f1: 
        x: 1
        f2: 
            x: 2
    __setup__:
        f1.x: 10
        f1.f2.x: 20
        f1.l[1].z: 200
        f1.d['b'].z: 400 
    """
    f = F0(**yaml.load( payload, yaml.CLoader))
    assert f.f1.f2.x == 20 
    assert f.f1.x == 10
    assert f.f1.l[1].z == 200
    assert f.f1.d['b'].z == 400


