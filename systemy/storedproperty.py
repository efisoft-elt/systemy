

def storedproperty(func):
    """ Decorator for a property stored inside the parent object
    
    The parameter is built ones and the property is stored inside 
    the parent.__dict__ 
    This is to be used when heavy property needs to be build the first time 
    it is used and to avoid to build an element at each access  
    
    Example::

        class A:
            ncall = 0 

            @storedproperty
            def prop(self):
                self.ncall += 1
                return self.ncall  
            
        a = A()
        assert a.prop == 1  # function called  
        assert a.prop == 1  # not called 
        assert a.prop == 1  # not called 
        del a.prop 
        assert a.prop == 2 # function called 
    """
    return StoredProperty()._set_builder(func)

class StoredProperty:
    _build_func = None
    _name = None 
    def __get__(self, owner, cls):
        if owner is None: return self
        if self._name is None:
            raise ValueError("Bug savedproperty has no name ")
        owner.__dict__[self._name] = self._build_func(owner)
        return  owner.__dict__[self._name] 
    
    def __set_name__(self, owner, name):
        self._name = name

    def _set_builder(self, func):
        self._build_func = func
        try:
            self.__doc__ = func.__doc__
        except AttributeError:
            pass
        return self
