from abc import ABC, abstractmethod
from enum import *

from . import *


class PropertyFlags(IntFlag):
    NONE = 0x00
    REPEATED = 0x01


class IntegerFormat(IntEnum):
    TIMESTAMP = 0x01
    METRIC_ID = 0x02
    TRIGGER_ID = 0x03
    PROFILE_ID = 0x04
    COMPONENT_ID = 0x05
    AVERAGE_TIME = 0x15
    TIME_DELTA = 0x16
    TIMEZONE_OFFSET = 0x17
    ASSOCIATED_TIME = 0x18
    PERIOD_IN_HOURS = 0x19
    TIME_OF_DAY = 0x1E
    SAMPLE_TIMESTAMP = 0x1F


class StringFormat(IntEnum):
    UNKNOWN = 0x00
    UUID = 0x01


class PropertyType(IntEnum):
    UNKNOWN = 0x00
    DOUBLE = 0x01
    FLOAT = 0x02
    INTEGER_64 = 0x03
    INTEGER = 0x04
    ERROR_CODE = 0x05
    INTEGER_32 = 0x06
    INTEGER_UNSIGNED = 0x07
    BYTE_COUNT = 0x08
    SEQUENCE_NUMBER = 0x09
    BEDF_OPERATOR = 0x0A
    BOOLEAN = 0x0C
    ENUM = 0x0B
    STRING = 0x0D
    BYTES = 0x0E
    PACKED_UINT_32 = 0x15
    PACKED_TIMES = 0x11
    PACKED_ERRORS = 0x14
    OBJECT = 0x1B


class PropertySensitivity(IntEnum):
    UNKNOWN = 0x00
    PUBLIC = 0x01
    PRIVATE = 0x02
    SENSITIVE = 0x03


class ManifestExtensionType(IntEnum):
    NONE = 0x00
    ADD_PROPERTY = 0x01
    UNKNOWN_2 = 0x02


class ManifestPropertyTag(IntEnum):
    TAG_INDEX = 0x01
    TAG_TYPE = 0x02
    TAG_FLAGS = 0x03
    TAG_NAME = 0x04
    TAG_PII = 0x05
    TAG_STRING_FORMAT = 0x06
    TAG_OBJECT_TYPE = 0x07
    TAG_ENUM_INDEX = 0x08
    TAG_INTEGER_FORMAT = 0x09
    TAG_EXTENSION = 0x0A
    TAG_EXTENSION_TARGET = 0x0B
    TAG_SENSITIVITY = 0x0C


class ManifestDefinitionTag(IntEnum):
    DEFINE_OBJECT = 0x01
    DEFINE_TYPE = 0x02


class ManifestTypeDefinitionTag(IntEnum):
    TAG_NAME = 0x01
    TAG_ENUM_MEMBER = 0x02
    TAG_ENUM_MEMBER_NAME = 0x1E


class ManifestObjectDefinitionTag(IntEnum):
    TAG_NAME = 0x01
    TAG_PROPERTY_DEFINITION = 0x02
    TAG_EXTEND = 0x0A


class ManifestEnumMemberTag(IntEnum):
    TAG_NAME = 0x01
    TAG_VALUE_INT = 0x02
    TAG_VALUE_SIGNED = 0x03


def to_type_descriptor(target: Union[None, int, 'ManifestDefinition']) -> Optional[str]:
    if target:
        if isinstance(target, int):
            return hex(target)

        if target.name:
            return target.name

        return hex(target)

    return None


class ManifestProperty:
    index: int
    name: Optional[str]
    type: PropertyType
    flags: PropertyFlags
    version: int
    pii: bool
    integer_format: Optional[IntegerFormat]
    string_format: Optional[StringFormat]
    object_type: Union[None, int, 'ManifestObjectDefinition']
    extension: ManifestExtensionType
    extends: Optional[Union[int, 'ManifestDefinition']]
    target: Union[None, int, 'ManifestDefinition']
    enum: Union[None, int, 'ManifestTypeDefinition']
    content: List[Tag]
    sensitivity: PropertySensitivity

    PROPERTY_MAP = {
        ManifestPropertyTag.TAG_NAME: 'name',
        ManifestPropertyTag.TAG_INDEX: 'tag',
        ManifestPropertyTag.TAG_TYPE: 'type',
        ManifestPropertyTag.TAG_FLAGS: 'flags',
        ManifestPropertyTag.TAG_PII: 'pii',
        ManifestPropertyTag.TAG_STRING_FORMAT: 'string_format',
        ManifestPropertyTag.TAG_OBJECT_TYPE: 'object_type',
        ManifestPropertyTag.TAG_ENUM_INDEX: 'enum',
        ManifestPropertyTag.TAG_INTEGER_FORMAT: 'integer_format',
        ManifestPropertyTag.TAG_EXTENSION: 'extends',
        ManifestPropertyTag.TAG_EXTENSION_TARGET: 'target',
        ManifestPropertyTag.TAG_SENSITIVITY: 'sensitivity'
    }

    def __str__(self):
        name = "anonymous" if self.name is None else self.name

        if self.type == PropertyType.OBJECT:
            object_target = f"class:{to_type_descriptor(self.object_type)} "
        else:
            object_target = ""

        if self.extends:
            object_extends = f"extends:{to_type_descriptor(self.extends)} "
        else:
            object_extends = ""

        return f"<PropertyDefinition {name} type:{repr(self.type)} tag:{hex(self.tag)} flags:{repr(self.flags)} " \
               f"{object_target}{object_extends}>"

    def __init__(self, parent):
        self.type = PropertyType.UNKNOWN
        self.name = None
        self.type_name = None
        self.parent = parent
        self.extends = None
        self.tag = 0x00
        self.pii = False
        self.extension = ManifestExtensionType.NONE
        self.integer_format = None
        self.string_format = None
        self.flags = PropertyFlags.NONE
        self.unknowns = {}

    def parse(self, content: bytes):
        self.content = decode_tags(content, ManifestPropertyTag)

        for tag in self.content:
            if tag.index == ManifestPropertyTag.TAG_TYPE:
                if tag.tag_type & TagType.LENGTH_PREFIX:
                    type_extended = io.BytesIO(tag.value)
                    while extend_tag := decode_tag(type_extended):
                        if extend_tag.index == 0x01:
                            self.type_name = extend_tag.value
                        else:
                            self.type = PropertyType(extend_tag.value)
                else:
                    self.type = PropertyType(tag.value)

            elif tag.index == ManifestPropertyTag.TAG_FLAGS:
                self.flags = PropertyFlags(tag.value)

            elif tag.index == ManifestPropertyTag.TAG_SENSITIVITY:
                self.sensitivity = PropertySensitivity(tag.value)

            elif tag.index == ManifestPropertyTag.TAG_INDEX:
                self.index = tag.value

            elif tag.index == ManifestPropertyTag.TAG_ENUM_INDEX:
                self.enum = tag.value

            elif tag.index == ManifestPropertyTag.TAG_PII:
                if tag.value == 0:
                    self.pii = False
                elif tag.value == 1:
                    self.pii = True
                else:
                    raise ManifestError(f"Unknown value for PII {tag.value}")

            elif tag.index == ManifestPropertyTag.TAG_OBJECT_TYPE:
                self.object_type = to_complete_tag(self.parent.category, tag.value)

            elif tag.index == ManifestPropertyTag.TAG_INTEGER_FORMAT:
                self.integer_format = IntegerFormat(tag.value)

            elif tag.index == ManifestPropertyTag.TAG_STRING_FORMAT:
                self.string_format = StringFormat(tag.value)

            elif tag.index == ManifestPropertyTag.TAG_NAME:
                self.name = tag.value.decode('utf-8')

            elif tag.index == ManifestPropertyTag.TAG_EXTENSION:
                self.extension = ManifestExtensionType(tag.value)

            elif tag.index == ManifestPropertyTag.TAG_EXTENSION_TARGET:
                if self.parent.index == 0:
                    self.extends = tag.value
                else:
                    self.extends = to_complete_tag(self.parent.category, tag.value)

            else:
                raise ManifestError(f"Unhandled tag {tag.index} with value {tag.value}")

        self.flags = PropertyFlags(self.flags)

        try:
            self.type = PropertyType(self.type)
        except ValueError:
            raise ManifestError(
                f"Unable to set type for property {self.name if self.name is not None else 'anonymous'} for class "
                "{self.parent.name} to type {hex(self.type)}")

    def bind(self, defs: Dict[int, 'ManifestDefinition']):
        if self.extends and isinstance(self.extends, int):
            if self.extends not in defs:
                print(f"Invalid Tag?")
            else:
                self.extends = defs[self.extends]

        if self.type == PropertyType.OBJECT and isinstance(self.object_type, int):
            if self.object_type not in defs:
                print(f"Invalid Tag?")
            else:
                self.object_type = defs[self.object_type]


T = TypeVar('T', bound='ManifestDefinition')


class ManifestDefinition(ABC):
    TAG = 0

    content: List[Tag]
    category: int
    index: int
    name: Optional[str]

    def __init__(self, category: int, index: int):
        self.category = category
        self.index = index
        self.name = '__anonymous__'

    def composite_tag(self) -> int:
        return to_complete_tag(self.category, self.index)

    @abstractmethod
    def parse(self, data: bytes):
        pass

    @classmethod
    def from_tag(cls: Type[T], category: int, index: int, tag: Tag) -> T:
        if tag.index != cls.TAG:
            raise ManifestError(f"Attempted to parse the wrong definition, value {tag.index} is not of type {cls.TAG}")
        return cls.from_bytes(category, index, tag.value)

    @classmethod
    def from_bytes(cls: Type[T], category: int, index: int, data: bytes) -> T:
        result = cls(category, index)
        result.parse(data)
        return result

    def bind(self, defs: Dict[int, 'ManifestDefinition']):
        pass


class ManifestEnumMember:
    name: str | int
    value: int
    display: str

    def __init__(self, index: int, data: bytes):
        self.index = index
        self.data = data
        reader = io.BytesIO(data)

        while tag := decode_tag(reader, ManifestEnumMemberTag):
            if tag.index == ManifestEnumMemberTag.TAG_NAME:
                if tag.value is str:
                    self.name = tag.value.decode('utf-8')
                else:
                    self.name = tag.value

            elif tag.index == ManifestEnumMemberTag.TAG_VALUE_INT:
                self.value = tag.value

            elif tag.index == ManifestEnumMemberTag.TAG_VALUE_SIGNED:
                # TODO: this is a special INT case - seems to be twos complement of length
                # encoded integer, value seen was '\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01'
                # implying signed int64

                self.value = tag.value

            else:
                raise ManifestError(f"Unknown tag type in EnumMember definition {hex(tag.index)} = {tag.value}")

    def __str__(self):
        return f"<ManifestEnumMember {self.name} = {hex(self.value)}>"


class ManifestTypeDefinition(ManifestDefinition):
    TAG = 2

    entries: List[ManifestEnumMember]
    extend: Union[None, int, 'ManifestDefinition']

    def __init__(self, category, index):
        super().__init__(category, index)
        self.content = []
        self.entries = []

    def __str__(self):
        return f"<ManifestTypeDefinition {self.name} value_count:{len(self.entries)}>"

    def parse(self, data: bytes):
        self.content = decode_tags(data, ManifestTypeDefinitionTag)

        for index, tag in enumerate(self.content):
            if tag.index == ManifestTypeDefinitionTag.TAG_NAME:
                self.name = tag.value.decode('utf-8')

            elif tag.index == ManifestTypeDefinitionTag.TAG_ENUM_MEMBER:
                self.entries.append(ManifestEnumMember(index, tag.value))

            else:
                raise ManifestError(f"Unknown property in type {self.name} - {tag.index} ({tag.value})")


class ManifestObjectDefinition(ManifestDefinition):
    TAG = 1

    properties: List[ManifestProperty]

    def __init__(self, category, index):
        super().__init__(category, index)

        self.properties = []
        self.content = []

    def __str__(self):
        if self.name is not None:
            return f"<ManifestObject name:{self.name} property_count:{len(self.properties)}>"
        else:
            return f"<ManifestObject __anonymous__ property_count:{len(self.properties)}>"

    def parse(self, content: bytes):
        self.content = decode_tags(content, ManifestObjectDefinitionTag)

        for tag in self.content:
            if tag.index == ManifestObjectDefinitionTag.TAG_PROPERTY_DEFINITION:
                prop = ManifestProperty(self)
                prop.parse(tag.value)
                self.properties.append(prop)

            elif tag.index == ManifestObjectDefinitionTag.TAG_NAME:
                self.name = tag.value

            else:
                raise ManifestError(f"Unknown tag {hex(tag.index)} in object {self.name}")

    def bind(self, defs: Dict[int, 'ManifestDefinition']):
        for prop in self.properties:
            prop.bind(defs)
