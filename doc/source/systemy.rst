Introduction
=============


:mod:`systemy` is a package aims to simplify the relation between a processor class and its data 
comming from several sources (e.g. config file, payload, etc ...) 

It is specialy usefull when building a scalable and hierarchical model of something or a simulator and keep te hability to 
have configuration outside the python space (e.g. yam file, json payload etc ...).   

Sub-system are included inside a system by instanciating a Factory to build the sub-system (within the context of its
parent) at run time. 

Factories and Factory's parameters are exposed to user payload or config file in order to build a System object which
handle any processings. 

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
    

The Config class act as a factory for House and Room. When instanciated and ``house.room`` is called, the room object is
built thanks to the config attributes and the ``build`` method located inside the ``Config`` Factory. 



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
    
Because the bedroom is declared with a BaseConfig class (actually is a :class:`systemy.BaseFactory`) it is automaticaly built has
a system the first time  `house.bedroom` is asked. This is the rule for every factory inside the config class: every
factory in the config class will be built from the `system.subsystem` attribute call.  Other parameters of config are
passed as is (they are however readonly).  

An other way to build a System is to start from the Config class and use its build method  

.. code-block:: python 

   house_configuration = House.Config( bedroom={'width': 7.0}) 
   house = house_configuration.build()
   assert house.bedroom.width == 7.0 

   house_configuration.bedroom.width = 11.0
   assert house.bedroom.width == 11.0 
   assert house.__config__ is house_configuration 

On the example above one can see that we can easely separate the configuration (data) space from the business of the system
class which can have many other ("private") parameters.

So the full description of hour `house` can be done inside a yaml file for instance: 


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
- ``!include:/path/to/file.yaml`` include in placve an other system factory     

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


1. By Allowing extra in the house model

.. code-block:: python 
    
    from systemy import BaseSystem

    class Room(BaseSystem):
        class Config:
            name: str = "unknown"
            width: float = 0.0
            depth: float = 0.0 
        def get_area(self):
            return self.width * self.depth

    class House:
        class Config:
            name: str = "unknown"
            class Config: #<--- This is the Config of pydantic. I knwon this is a bit confusing 
                extra = "allow"
        

        def get_area(self):
            return sum( room.get_area() for room in self.find(Room))
                
    house_config = House.Config(  bedroom=Room.Config(name="my bedroom"), toilet=Room.Config(name="toilet") ) 
    house = house_config.build()
    
    assert house.bedroom.name == "my bedroom"    

Note, one can easely find all Rooms inside the house: 


.. code-block:: python 

   for room in house.find( Room):
        print(room.name)

2. By Adding a List or a Dict of Room.Config 


.. code-block:: python 

    from systemy import BaseSystem, SystemLoader, register_factory
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
            room_list: List[Room.Config] = []
            room_dict: Dict[str, Room.Config] = {}
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

systemy recognised the list and dict of factory so it has built the house attributes ``room_list`` and ``room_dict``.
This should work only when the typing is ``List[C]`` ``Dict[Any,C]`` where ``C`` is a class with base
:class:`systemy.BaseFactory` 

3. By customizing a Factory for the House


.. code-block:: python 

    import BaseSystem, SystemLoader, register_factory, BaseFactory
    import yaml 

    
    class Room(BaseSystem):
        class Config:
            name: str = "unknown"
            width: float = 0.0
            depth: float = 0.0
    
    class Studio(BaseSystem):
        class Config:
            name: str = "unknown"
            main_room = Room.Config()
            toilet = Room.Config()

    class Appartment(BaseSystem):
        class Config:
            name: str = "unknown"
            main_room = Room.Config()
            bedroom = Room.Config()
            toilet = Room.Config()
    
    @register_factory("House")
    class HouseFactory(BaseFactory, extra="allow"):
        type: str = "StudioConfig"
        
        def build(self, parent=None, name=""):
            if self.type == "Studio":
                Factory = Studio.Config
            elif self.type == "Appartment":
                Factory = Appartment.Config
            else:
              raise ValueError(f"unknown house type {self.type}")
            return Factory.parse_obj( self.dict(exclude=set(['type']))).build(parent, name) 
            
    src = """!factory:House 
    type: "Appartment"
    bedroom:
        name: "My Appartment bedroom"
    
    """
    
    house_config = yaml.load( src, SystemLoader)
    house = house_config.build()
    assert house.bedroom.name == 'My Appartment bedroom'
    assert isinstance(house, Appartment)

One can mutate the crested system class function to a type a model or whatever inside the Factory.


On creating a System 
--------------------

Following the first above exemple, these ways of creating a system are all iddentical:

.. code-block:: python 

   house = House( bedroom={'width': 12} )


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



