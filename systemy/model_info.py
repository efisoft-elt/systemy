# ##################################################################
#
#        Model Info Extractor 
#
# ##################################################################

# ##################################################################
# Not yet part of the API !!!!



from dataclasses import dataclass, field
from typing import Iterable, Optional, Tuple, Type, Union
from pydantic import BaseModel, create_model
from systemy.system import get_model_fields

@dataclass
class DataModelInfoExtractor:
    InfoStructure: BaseModel 
    include: Optional[Iterable] = None 
    exclude: Iterable = field(default_factory=set)
    include_type : Optional[Union[Type,Tuple[Type]]] = None
    exclude_type: Optional[Union[Type,Tuple[Type]]] = None

    def __post_init__(self):
        self.field_extractor = ModelInfoFieldExtractor( self.InfoStructure)


    def extract(self, Model: Type[BaseModel], name=None, base=None):
                
        infos = {}
        fields = get_model_fields(Model)
        if self.include is not None:
            def iterator():
                for name in set(self.include):
                    yield name, fields[name] 
        else:
            iterator = fields.items
        
        for name, field in iterator():
            if name in self.exclude: 
                continue
            if self.exclude_type:
                if issubclass( field.type_, self.exclude_type):
                    continue
            if issubclass(field.type_, BaseModel):
                infos[name] = self.extract( field.type_)()
            else:
                if self.include_type:
                    if not issubclass( field.type_, self.include_type): continue 
                        
                infos[name] = (self.InfoStructure, self.field_extractor.extract(field))
        if name is None:
            name = "Info"+Model.__name__
        return create_model(name,__base__ = base, **infos)


@dataclass 
class ModelInfoFieldExtractor:
    InfoStructure: BaseModel
    def __post_init__(self):
        try:
            if issubclass( self.InfoStructure, BaseModel):
                info_fields = get_model_fields(self.InfoStructure)
            else:
                info_fields = self.InfoStructure.__dataclass_fields__
        except (ValueError, AttributeError, TypeError) as er:
            raise ValueError("Probably Bad InfoStructure, shall be a BaseModel Type or a dataclass type") from er

        def extract(field):
            extras = field.field_info.extra
            values = {}
            for name in info_fields:
                if name == "default":
                    values[name] = field.get_default()
                    continue 
                
                try:
                    val = getattr(field.field_info, name)
                except AttributeError:
                    try:
                        val = extras[name]
                    except KeyError:
                        pass 
                    else:
                        values[name] = val 
                else:
                    if val is not None:
                        values[name] = val 
    
            return self.InfoStructure(**values) 
        self.extract = extract

def create_model_info(
        Model: Type[BaseModel],  
        InfoStructure: Type[BaseModel],
        include: Optional[Iterable] = None, 
        exclude: Iterable = None, 
        include_type: Union[Type,Tuple[Type]] = None, 
        exclude_type: Union[Type,Tuple[Type]] = None, 
        name: str =None, 
        base: Type = None
    ) -> Type[BaseModel]:
    """ create a pydantic model representing all information found in an other model class 

    Args:
        Model  (Type[BaseModel]): a Model with some value and some extra field information 
        InfoStructure (Type[BaseModel]): The Model representing information to be extracted 
        include (Optional, Set[str]): A set of member name to include 
        exclude (Optional, Set[Str]): A sett of member to exclude  
        include_type: (Optional, Type, Tuple[Type]): include only members with the given type(s)
        exclude_type: (Optional, Type, Tuple[Type]): exclude member with the given type(s) 
    """
    if exclude is None: exclude = set()
    
    return DataModelInfoExtractor(
            InfoStructure, include=include, exclude=exclude, 
            include_type=include_type, exclude_type=exclude_type
        ).extract(Model, name=name, base=base)

