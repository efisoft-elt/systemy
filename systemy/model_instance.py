
from pydantic import ValidationError, BaseModel

from systemy.loaders import get_factory_class

def all_subclasses(cls):
    return list(cls.__subclasses__()) +\
        [s for c in cls.__subclasses__() for s in all_subclasses(c)]

# simple solution for the record 
# from typing import Union
# class ModelInstanceMeta(type):
#     def __getitem__(cls, item):
#         if isinstance(item, tuple):
#             raise ValueError("ModelInstance takes only one subfield ")
#         # quizz of the order ??
#         subclasses = tuple(all_subclasses(item)[::-1])
#         if not subclasses:
#             raise ValueError(f"Base class {item.__name__} has no subclass")
#         if len(subclasses)==1:
#             return subclasses[0]
#         return Union.__getitem__(subclasses)
        
# class ModelInstance(metaclass=ModelInstanceMeta):
#     pass


class InstanceOfMeta(type):
    def __getitem__(cls, item):
        if isinstance(item, tuple):
            raise ValueError("ModelInstance takes only one subfield ")
        # quizz of the order ?? 
        return type("ModelInstance["+item.__name__+"]", (cls,), {'__BaseClass__': item})


class InstanceOf(metaclass=InstanceOfMeta):
    __BaseClass__ = BaseModel
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate 

    @classmethod
    def validate(cls, value):
        if isinstance( value, cls.__BaseClass__ ):
            return value 
        
        errors = []

        if isinstance( value, dict):
            factory = value.pop("__factory__", None)
            if factory:
                Factory = get_factory_class( factory )
                if not issubclass( Factory, cls.__BaseClass__):
                    raise ValueError( f"Factory {factory} is not aa subclass of {cls.__BaseClass__.__name__}")
                return Factory.validate(value)  
        
        #################
        # replace this to something more custom if needed 
        for SubClass in all_subclasses(cls.__BaseClass__)[::-1]:
            for validator in SubClass.__get_validators__():
                try:
                    return validator(value)
                except (ValidationError, ValueError, AttributeError, KeyError) as err:
                    errors.append(err)
        #################
        if errors:
            raise ValueError( "\n".split( errors ))
        else:
            raise ValueError( ['cannot find a valid subclass'], cls)


