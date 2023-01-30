from systemy  import storedproperty





def test_stored_property_returns():
    class A:
        @storedproperty
        def prop(self):
            return 10.0 
    
    a = A()
    assert a.prop == 10.0 
    assert a.prop == 10.0
    a.prop = 2.0 
    assert a.prop == 2.0

def test_strored_property_builder_should_be_called_ones():
    class A:
        ncall = 0 

        @storedproperty
        def prop(self):
            self.ncall += 1
            return self.ncall  
        
    a = A()
    assert a.prop == 1  
    assert a.prop == 1
    assert a.prop == 1
    del a.prop 
    assert a.prop == 2

def test_stored_property_has_doc():
    
    class A:
        ncall = 0 

        @storedproperty
        def prop(self):
            """PROP"""
    
    assert A.prop.__doc__ == """PROP""" 


if __name__=="__main__":
    class A:
        ncall = 0 

        @storedproperty
        def prop(self):
            self.ncall += 1
            return self.ncall  
    a = A()
    import time 
    t1 = 0.0
    t2 = 0.0 
    
    for i in range(1000):

        tic = time.time()
        a.prop 
        toc = time.time()
        t1 += toc-tic

    
        tic = time.time()
        a.prop 
        toc = time.time()
        t2 += toc-tic 
        
        del a.prop
    
    print( t1, t2, t1/t2)
