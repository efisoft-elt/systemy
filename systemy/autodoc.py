from dataclasses import dataclass
from typing import Any, Dict, Union
from pydantic.fields import ModelField
from systemy.system import BaseFactory, BaseSystem, get_factory, get_factory_fields, get_model_fields , FactoryField

import re

@dataclass
class FieldInfo:
    description: str = "" 
    type_name: str = ""
    default: Any = None 
    unit: str = ""

    @classmethod
    def from_field(cls,  field: ModelField)-> "FieldInfo":
        return cls(
                description = field.field_info.description or "", 
                type_name= getattr(field.type_, "__name__", "") ,
                default = field.get_default(), 
                unit = field.field_info.extra.get("unit", "")
            )

def _field_config_line(attr: str, info: FieldInfo, indent="") -> str:
    sep= ":" if info.description else ""
    unit = " ["+info.unit+"]" if info.unit else "" 
    description = ("\n"+indent+"  ").join(  info.description.split("\n") )
    return f"{indent}{attr} ({info.type_name}, {info.default!r}){unit}{sep} {description}" 


def _config_doc(fields: Dict[str, ModelField], factories: Dict[str, FactoryField], exclude, indent: str= ""):
    lines = []
    for attr, field in fields.items():
        if attr in exclude: continue 
        # if attr in factories:
        #     pass 
        # else:
        #     lines.append( indent_text +_field_config_line( attr, field))
        lines.append( _field_config_line( attr, FieldInfo.from_field(field), indent ) )
    return "\n".join( lines) 

_indents_before_auto_doc = re.compile( r"^([\t ]*)__autodoc__", re.MULTILINE )
def _redocument_system(System: BaseSystem, exclude=set()):
    doc = System.__doc__ 
    if doc is None:
        doc = f"{System.__qualname__}\n__autodoc__"
        return 
    elif "__autodoc__" not in doc:
        return
    
    indent,*_ = _indents_before_auto_doc.findall(doc)
    indent = indent.strip('\n')
    auto_doc  = indent+"Config:\n"
    auto_doc += _config_doc( 
            get_model_fields( System.Config),
            get_factory_fields(System.Config) , 
            exclude,
            indent=indent+"  "
            )
    auto_doc += indent+"\n"
    doc = doc.replace( indent+"__autodoc__", auto_doc)

    System.__doc__ = doc 

def _redocument_factory(Factory: BaseFactory, exclude=set()):
    doc = Factory.__doc__ 
    if doc is None:
        try:
            System = Factory.get_system_class()
        except ( ValueError, NotImplementedError ):
            system_name = " to unknow System "
        else:
            system_name = f" builds {System.__qualname__}"

        doc = f"""Factory {Factory.__qualname__}{system_name}\n    \n    __autodoc__"""
        
    elif "__autodoc__" not in doc:
        return
    indent,*_ = _indents_before_auto_doc.findall(doc)
    indent = indent.strip('\n')

    auto_doc  = indent+"Params:\n"
    auto_doc += _config_doc( get_model_fields( Factory), get_factory_fields(Factory) , exclude, indent=indent+"  " )
    auto_doc += indent+"\n"
    doc = doc.replace( indent+"__autodoc__", auto_doc)
    Factory.__doc__ = doc 




def autodoc(SystemOrFactory: Union[BaseSystem, BaseFactory] = None , exclude=set()):
    """ decorator for System object 
    
    On a System: 
        The decorator looks for __autodoc__ flag inside the __doc__ and replace 
        it with information about variables inside the default `Config` factory class. 
        Then decorate the factory 
    On a Factory:
        Look for __autodoc__ flag inside the __doc__ and replace it with 
        Factory parameters information. 

    The pydantic.Field "description" keyword is used to comment parameters as well as the
        optional extra "unit" keyword. 
    """
    def autodocer(SystemOrFactory):
        if issubclass(SystemOrFactory , BaseSystem):
            _redocument_system(SystemOrFactory, exclude=exclude)
            _redocument_factory( SystemOrFactory.Config, exclude=exclude)
        else:
            _redocument_factory(SystemOrFactory, exclude=exclude)
        return SystemOrFactory 
    if SystemOrFactory is None:
        return autodocer
    else:
        return autodocer(SystemOrFactory)


if __name__== "__main__":
    from pydantic import Field  
    class B(BaseSystem):
        class Config:
            """ __autodoc__ """
            
    @autodoc(exclude={""})
    class S(B):
        """My system

        Hello 

        __autodoc__
        ---

        __autodoc__
        """
        class Config:
            scale: float = Field( 1.0, description="Scale of the Node\n Multiline \n description", unit="AU/mm")
            other: int = 9
    autodoc(S.Config)
    print( S.__doc__)
    print("========================")
    print( S.Config.__doc__ )

    
    
    

