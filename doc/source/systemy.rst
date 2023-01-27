Introduction
=============


:mod:`systemy` is a package aims to simplify handling of factories and what they are building. 
In short, a factory added as a member inside a "System" class automaticaly build a subsystem 
in context of its parent.     


It is specialy usefull when building a scalable and hierarchical model of something or a simulator
and keep te hability to have configuration outside the python space (e.g. yam file, json payload etc ...).   


Factories and Factory's parameters are exposed to user payload or config file in order to build a System object which
handle any processings. 

Factories are based on pydantic BaseModel. 

One special Factory is named **Config** and is part of any System class.



Installation
============ 

::

    > pip install systemy 



Getting Started
===============

Let start with an exemple of the description of a typical House with several rooms. 


.. code-block:: python 
    
    from systemy import BaseSystem 

    class Room(BaseSystem):
        class Config:
            name: str = "unknown"
            width: float = 0.0
            depth: float = 0.0
        
        def get_area(self):
            return self.width * self.depth 

    class House(BaseSystem):
        class Config:
            name: str  = "unknown"
            bedroom = Room.Config(name="Bedroom", width=10, depth=4)
            kitchen = Room.Config(name="kithen", width=12, depth=9) 
        
        def get_area(sefl):
            return self.bedroom.get_area() + self.kithen.get_area()
    

The Config class act as a factory for House and Room. When instanciated and ``house.room`` is reached,  
the room object is built thanks to the config attributes and the ``build`` method 
located inside the ``Config`` Factory (like for any factory).
The __init__ method of a room axcept then all argument defined inside the Config class.  



.. note::

    The class Config is automaticaly trasnformed to a pydantic model with the ineritance of parent system class config.

    So doing this :

    .. code-block:: python 

        class Room(BaseSystem):
            class Config:
                ...

    Is equivalent in doing: 

    .. code-block:: python 

        class Room(BaseSystem):
            class Config(BaseSystem.Config):
                ...
                
    However, Everything in the config space can be accessed through the System class attribute: 


.. code-block:: python 

   house = House()
   assert house.bedroom.width == 10
    
Because the bedroom is implemented in the class with a Factory (the .Config factory in this case) 
it is automaticaly built as a system the first time  `house.bedroom` is reached. 
This is the rule for every factory inside the config class.

Other parameters inside Config are accessible through the class but are readonly by default. 
You can change this default behaviour by setting ``_allow_config_assignment`` to ``True`` 
inside the System class: 

.. code-block:: python

    class Room(BaseSystem):
        _allow_config_assignment = True 
        ...
    
    #or 

    class Room(BaseSystem, allow_config_assignment = True):
        pass

An other way to build a System is to start from the Config class and use its build method  

.. code-block:: python 

   house_configuration = House.Config( bedroom={'width': 7.0}) 
   house = house_configuration.build()
   assert house.bedroom.width == 7.0 

   house_configuration.bedroom.width = 11.0
   assert house.bedroom.width == 11.0 
   assert house.__config__ is house_configuration 

On the example above one can see that we can easely separate the configuration (data) space from the business 
of the system class which can have many other ("private") parameters.

So the full description of our `house` can be done inside a yaml file for instance: 


.. code-block:: python 

   import yaml
   
   src = """
   bedroom:
        name: my bedroom 
        width: 4
        depth: 3
   kitchen:
        name: my kitchen
   """
   
   house_config = House.Config( **yaml.load( src, yaml.CLoader))
   house = house_config.build()
  
systemy also provide a loader with 3 custom tags, e.g.:

- ``!factory:FactoryName`` Declare the mapping with the given Factory name (see bellow)
- ``!math sin(pi/3)``  return some math results on the fly for conveniance 
- ``!include:/path/to/file.yaml`` include in place an other system factory     

To use the ``!factory:`` tag one need to register the targeted factory to the system. 


.. code-block:: python 

   from systemy import BaseSystem, register_factory 
    
   @register_factory
   class Room(BaseSystem):
        class Config:
            name: str = "unknown"
            width: float = 0.0
            depth: float = 0.0 
        
        def get_area(self):
            return self.width * self.depth
   @register_factory 
   class House(BaseSystem):
        class Config:
            name: str  = "unknown"
            bedroom = Room.Config(name="Bedroom", width=10, depth=4)
            kitchen = Room.Config(name="kithen", width=12, depth=9) 
         
        def get_area(sefl):
            return self.bedroom.get_area() + self.kithen.get_area()

By default register_factory takes the class Name for the registery but this can be changed e.g. :


.. code-block:: python 
   
    @register_factory("House2") 
    class House(BaseSystem):
        class Config:
            ...


Ones registered on can use directly the :class:`systemy.SystemLoader`


.. code-block:: python 

   from systemy import SystemLoader
   import yaml 
   
   src = """!factory:House
   bedroom:
        name: my bedroom 
        width: 4
        depth: 3
   kitchen:
        name: my kitchen
   """
   house = yaml.load( src, SystemLoader).build()
    
On the example above we didn't need to declare the bedroom's and kithen's factory because it is defined inside the
model. 

Let us see how to define an House model with more flexible user configuration for the rooms (sub-systems). 

They are several ways to do that: 


1. By Allowing extra in the house system class 

.. code-block:: python 
    
    from systemy import BaseSystem

    class Room(BaseSystem):
        class Config:
            name: str = "unknown"
            width: float = 0.0
            depth: float = 0.0 
        def get_area(self):
            return self.width * self.depth

    class House(BaseSystem, extra="allow"):
        class Config:
            name: str = "unknown"

        def get_area(self):
            return sum( room.get_area() for room in self.find(Room))
    
    house = House( 
        bedroom=Room.Config(name="my bedroom", width=4.0, depth=3.0), 
        toilet=Room.Config(name="toilet", width=1.5, depth=1.0) 
    )


    
    assert house.bedroom.name == "my bedroom"    
    assert house.get_area() == 13.5 

For more information about the extra configuration, please see pydantic documentation. 



Note, one can easely find all Rooms inside the house: 


.. code-block:: python 

   for room in house.find( Room):
        print(room.name)

2. By Adding a List or a Dict of Room.Config 

.. code-block:: python 

    from systemy import BaseSystem, SystemLoader, register_factory, FactoryList, FactoryDict
    import yaml 

    class Room(BaseSystem):
        class Config:
            name: str = "unknown"
            width: float = 0.0
            depth: float = 0.0
    
    @register_factory
    class House(BaseSystem):
        class Config:
            name: str = "unknown"
            room_list: FactoryList[Room.Config] = []
            room_dict: FactoryDict[str, Room.Config] = {}
        def get_area(self):
            return sum( room.get_area() for room in self.room_list)


    src = """!factory:House
    room_list:
        - width: 13
          depth: 12
          name: Kitchen 
        - width: 2 
          depth: 1 
          name: Toilet 
    room_dict: 
        kitchen: 
            width: 13
            depth: 12
            name: Kitchen 
        toilet:
            width: 2 
            depth: 1 
            name: Toilet 
    """
    house_config = yaml.load( src, SystemLoader)
    house = house_config.build()
    
    assert house.room_list[0].name == "Kitchen"
    assert house.room_dict['toilet'].name == "Toilet"

.. warning::

   Before v2.0 implicit  ``List[Room.Config]`` was understood as FactoryList[Room.Config]. 
   It was a mistake and is no longer supported.  


3. By customizing a Factory for the House


.. code-block:: python 

    from systemy import BaseSystem, SystemLoader, register_factory, BaseFactory, factory
    import yaml 
    
    class House(BaseSystem):
        ...
    
    class Room(BaseSystem):
        class Config:
            name: str = "unknown"
            width: float = 0.0
            depth: float = 0.0
    
    class Studio(House):
        class Config:
            name: str = "unknown"
            main_room = Room.Config()
            toilet = Room.Config()

    class Appartment(House):
        class Config:
            name: str = "unknown"
            main_room = Room.Config()
            bedroom = Room.Config()
            toilet = Room.Config()
    
    @register_factory("House")
    @factory(House)
    class HouseFactory(BaseFactory, extra="allow"):
        type: str = "Studio"
        
        def build(self, parent=None, name=""):
            if self.type == "Studio":
                Factory = Studio.Config
            elif self.type == "Appartment":
                Factory = Appartment.Config
            else:
              raise ValueError(f"unknown house type {self.type}")
            return Factory.parse_obj( self.dict(exclude={'type'})).build(parent, name) 
            
    src = """!factory:House 
    type: "Appartment"
    bedroom:
        name: "My Appartment bedroom"
    
    """
    
    house_config = yaml.load( src, SystemLoader)
    house = house_config.build()
    assert house.bedroom.name == 'My Appartment bedroom'
    assert isinstance(house, Appartment)

One can mutate the created system class function to a type a model or whatever inside the Factory.

On the example above ``@factory(House)`` decorator is optional but is implemented the ``get_system_class`` classmethod 
function as a weak reference of the House System. So one can now by introspection the targeted 
class by the factory.  In the future the @factory can make also some sanity checks. 


About creating a System 
--------------------

Following the first above exemple, these ways of creating a system are all iddentical:

.. code-block:: python 

   house = House( bedroom={'width': 12} ) # works only if bedroom is declared in the model 


.. code-block:: python 

   house = House( bedroom=Room.Config(width=12) )

.. code-block:: python 
   
   house_config = House.Config (bedroom = {'width':12})
   house = house_config.build() 

.. code-block:: python 
   
   house_config = House.Config (bedroom = {'width':12})
   house = House( __config__=house_config )


.. code-block:: python 
   data = {'bedroom':{'width':12}}   
   house_config = House.Config.from_obj(data)
   house = House.Config.from_obj(data).build()

The build method is accepting two optional arguments: the parent system and the name in the context of its parent. 
So when we do :

.. code-block:: python 

   bedroom = house.bedroom 

This can be decomposed this way : 

.. code-block:: python 

    bedroom = Room.Config().build( house, "bedroom") 

The path way of subsystem is stored in a string in the `__path__` attribute 

Searching the subs-system factories of a System Class 
-----------------------------------------------------

.. code-bock:: python 
    
    from systemy import find_factories 
    
    class Room(BaseSystem):
        class Config:
            area = 0.0

    class House(BaseSystem):
        class Config:
            room1 = Room.Config(area=11.0) # part of the config space 
        room2 = Room.Config(area=12.0) # not configurable 
        room3 = Room.Config(area=13.0) # not configurable 

    for name, factory in find_factories(House, Room):
        print(name, factory.area )
    
    ## prints 
    # room1 11.0
    # room2 12.0
    # room3 13.0    

On the exemple ablove we are looking for ``Room`` factories inside an ``House`` class. Contrary to the
``house.find(House)`` method called on an instance of house, ``find_factories`` returns a pair of name 
and ``Factory`` and do not have recursive possibility. 


About factory accessibility
---------------------------

A side note from the last example:   room1 is part of the config space, it can be accessed at __init__ of house while 
room2 and room3 are defined inside the system class and therefore are not configurable at __init__.  

.. code-block:: python 
    
   # this is okay  
   house = House( room1=Room(area=10)) 
    
   # this is not okay 
   house = House( room2=Room(area=10)) 

    ValidationError: 1 validation error for House.Config
    room2
      extra fields not permitted (type=value_error.extra)

A difference is also that factories inside a class are accessible from the class but not factories 
inside the Config class (it is due to pydantic behavior). 







