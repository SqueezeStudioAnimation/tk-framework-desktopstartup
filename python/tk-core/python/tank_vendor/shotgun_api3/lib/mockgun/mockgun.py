"""
 -----------------------------------------------------------------------------
 Copyright (c) 2009-2017, Shotgun Software Inc

 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions are met:

  - Redistributions of source code must retain the above copyright notice, this
    list of conditions and the following disclaimer.

  - Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.

  - Neither the name of the Shotgun Software Inc nor the names of its
    contributors may be used to endorse or promote products derived from this
    software without specific prior written permission.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

-----------------------------------------------------------------------------



-----------------------------------------------------------------------------
M O C K G U N 
-----------------------------------------------------------------------------

Experimental software ahead!
----------------------------
Disclaimer! Mockgun is in its early stages of development. It is not fully 
compatible with the Shotgun API yet and we offer no guarantees at this point 
that future versions of Mockgun will be backwards compatible. Consider this 
alpha level software and use at your own risk. 


What is Mockgun?
----------------
Mockgun is a Shotgun API mocker. It's a class that has got *most* of the same
methods and parameters that the Shotgun API has got. Mockgun is essentially a 
Shotgun *emulator* that (for basic operations) looks and feels like Shotgun.

The primary purpose of Mockgun is to drive unit test rigs where it becomes
too slow, cumbersome or non-practical to connect to a real Shotgun. Using a 
Mockgun for unit tests means that a test can be rerun over and over again 
from exactly the same database state. This can be hard to do if you connect
to a live Shotgun instance.  


How do I use Mockgun?
---------------------
First of all, you need a Shotgun schema to run against. This will define
all the fields and entities that mockgun will use. Simply connect to 
your Shotgun site and use the generate_schema() method to download
the schema data:

    # connect to your site
    from shotgun_api3 import Shotgun
    sg = Shotgun("https://mysite.shotgunstudio.com", script_name="xyz", api_key="abc")
    
    # write out schema data to files
    from shotgun_api3.lib import mockgun
    mockgun.generate_schema(sg, "/tmp/schema", "/tmp/entity_schema")
    
Now that you have a schema, you can tell your mockgun instance about it.
We do this as a class-level operation, so that the consctructor can be 
exactly like the real Shotgun one:

    from shotgun_api3.lib import mockgun
    
    # tell mockgun about the schema
    mockgun.Shotgun.set_schema_paths("/tmp/schema", "/tmp/entity_schema")
    
    # we are ready to mock! 
    # this call will not connect to mysite, but instead create a 
    # mockgun instance which is connected to an *empty* shotgun site
    # which has got the same schema as mysite.
    sg = mockgun.Shotgun("https://mysite.shotgunstudio.com", script_name="xyz", api_key="abc")

    # now you can start putting stuff in
    print sg.create("HumanUser", {"firstname": "John", "login": "john"})
    # prints {'login': 'john', 'type': 'HumanUser', 'id': 1, 'firstname': 'John'}
 
    # and find what you have created
    print sg.find("HumanUser", [["login", "is", "john"]])
    prints [{'type': 'HumanUser', 'id': 1}]
    
That's it! Mockgun is used to run the Shotgun Pipeline Toolkit unit test rig.

Mockgun has a 'database' in the form of a dictionary stored in Mockgun._db
By editing this directly, you can modify the database without going through 
the API.


What are the limitations?
---------------------
There are many. Don't expect mockgun to be fully featured at this point.
Below is a non-exhaustive list of things that we still need to implement:

- Many find queries won't work
- Methods around session handling and authentication is not implemented
- Attachments and upload is rundimental at best
- Schema modification isn't most most likely will never be supported
- There is no validation or sanitation

"""

import copy
import datetime

from ... import sg_timezone, ShotgunError
from ...shotgun import _Config
from .errors import MockgunError
from .schema import SchemaFactory

# ----------------------------------------------------------------------------
# Version
__version__ = "0.0.1"


# ----------------------------------------------------------------------------
# API

class Shotgun(object):
    """
    Mockgun is a mocked Shotgun API, designed for test purposes.
    It generates an object which looks and feels like a normal Shotgun API instance.
    Instead of connecting to a real server, it keeps all its data in memory in a way
    which makes it easy to introspect and test.
    
    The methods presented in this class reflect the Shotgun API and are therefore
    sparsely documented.
    
    Please note that this class is built for test purposes only and only creates an
    object which *roughly* resembles the Shotgun API - however, for most common 
    use cases, this is enough to be able to perform relevant and straight forward 
    testing of code.
    """

    __schema_path = None
    __schema_entity_path = None

    @classmethod
    def set_schema_paths(cls, schema_path, schema_entity_path):
        """
        Set the path where schema files can be found. This is done at the class
        level so all Shotgun instances will share the same schema.
        The responsability to generate and load these files is left to the user
        changing the default value.
        
        :param schema_path: Directory path where schema files are.
        """
        cls.__schema_path = schema_path
        cls.__schema_entity_path = schema_entity_path

    @classmethod
    def get_schema_paths(cls):
        """
        Returns a tuple with paths to the files which are part of the schema.
        These paths can then be used in generate_schema if needed.
        
        :returns: A tuple with schema_file_path and schema_entity_file_path
        """
        return (cls.__schema_path, cls.__schema_entity_path)

    def __init__(self,
                 base_url,
                 script_name=None,
                 api_key=None,
                 convert_datetimes_to_utc=True,
                 http_proxy=None,
                 ensure_ascii=True,
                 connect=True,
                 ca_certs=None,
                 login=None,
                 password=None,
                 sudo_as_login=None,
                 session_token=None,
                 auth_token=None):

        # emulate the config object in the Shotgun API.
        # these settings won't make sense for mockgun, but
        # having them present means code and get and set them
        # they way they would expect to in the real API.
        self.config = _Config()
        
        # load in the shotgun schema to associate with this Shotgun
        (schema_path, schema_entity_path) = self.get_schema_paths()

        if schema_path is None or schema_entity_path is None:
            raise MockgunError("Cannot create Mockgun instance because no schema files have been defined. "
                               "Before creating a Mockgun instance, please call Mockgun.set_schema_paths() "
                               "in order to specify which Shotgun schema Mockgun should operate against.")
        
        self._schema, self._schema_entity = SchemaFactory.get_schemas(schema_path, schema_entity_path)

        # initialize the "database"
        self._db = dict((entity, {}) for entity in self._schema)

        # set some basic public members that exist in the Shotgun API
        self.base_url = base_url
        
        # bootstrap the event log
        # let's make sure there is at least one event log id in our mock db
        data = {}
        data["event_type"] = "Hello_Mockgun_World"
        data["description"] = "Mockgun was born. Yay."
        self.create("EventLogEntry", data)

        self.finds = 0

        self._current_user = None
    ###################################################################################################
    # public API methods
    def set_current_user(self, sg_user):
        # Used to fill the 'created_by' field automatically.
        self._current_user = sg_user

    def schema_read(self):
        return self._schema

    def schema_field_create(self, entity_type, data_type, display_name, properties=None):
        raise NotImplementedError
    
    def schema_field_update(self, entity_type, field_name, properties):
        raise NotImplementedError

    def schema_field_delete(self, entity_type, field_name):
        raise NotImplementedError
    
    def schema_entity_read(self):
        return self._schema_entity

    def schema_field_read(self, entity_type, field_name=None):
        if field_name is None:
            return copy.copy(self._schema[entity_type])  # prevent artifacts
        else:
            return dict((k, v) for k, v in self._schema[entity_type].items() if k == field_name)

    def find(self, entity_type, filters, fields=None, order=None, filter_operator=None, limit=0, retired_only=False, page=0):
        self.finds += 1

        self._validate_entity_type(entity_type)
        # do not validate custom fields - this makes it hard to mock up a field quickly
        #self._validate_entity_fields(entity_type, fields)

        # Configure fields
        if fields is None:
            requested_fields = set(["type", "id"])
        else:
            requested_fields = set(fields) | set(["type", "id"])

        # Include fields from the order argument in the searched fields
        order_fields = set()
        if order:
            for o in order:
                order_fields.add(o['field_name'])

        # Merge the requested fields and the order fields.
        # We need all those to property order the results but still return only requested fields.
        all_fields = set()
        all_fields.update(requested_fields)
        all_fields.update(order_fields)

        # FIXME: This should be refactored so that we can use the complex filer
        # style in nested filter operations.
        if isinstance(filters, dict):
            # complex filter style!
            # {'conditions': [{'path': 'id', 'relation': 'is', 'values': [1]}], 'logical_operator': 'and'}

            resolved_filters = []
            for f in filters["conditions"]:

                if f["path"].startswith("$FROM$"):
                    # special $FROM$Task.step.entity syntax
                    # skip this for now
                    continue

                if len(f["values"]) != 1:
                    # {'path': 'id', 'relation': 'in', 'values': [1,2,3]} --> ["id", "in", [1,2,3]]
                    resolved_filters.append([ f["path"], f["relation"], f["values"] ])
                else:
                    # {'path': 'id', 'relation': 'is', 'values': [3]} --> ["id", "is", 3]
                    resolved_filters.append([ f["path"], f["relation"], f["values"][0] ])

        else:
            # traditional style sg filters
            resolved_filters = filters

        results = [
            # Apply the filters for every single entities for the given entity type.
            row for row in self._db[entity_type].values()
            if self._row_matches_filters(
                entity_type, row, resolved_filters, filter_operator, retired_only
            )
        ]

        # Extract fields from row
        val = [dict((field, self._get_field_from_row(entity_type, row, field)) for field in all_fields) for row in results]

        # Add the special 'name' field on the entity and multi-entity values.
        val = [dict((field_name, self._handle_name_field(field_value)) for field_name, field_value in item.iteritems()) for item in val]

        # Handle the ordering of the result after we requested additional fields from results.
        if order:
            # order: [{"field_name": "code", "direction": "asc"}, ... ]
            for order_entry in order:
                if "field_name" not in order_entry:
                    raise ValueError("Order clauses must be list of dicts with keys 'field_name' and 'direction'!")

                order_field = order_entry["field_name"]
                if order_entry["direction"] == "asc":
                    desc_order = False
                elif order_entry["direction"] == "desc":
                    desc_order = True
                else:
                    raise ValueError("Unknown ordering direction")

                val = sorted(val, key=lambda k: k[order_field], reverse=desc_order)

        # Remove any fields that was not explicitely requested.
        fields_to_remove = all_fields - requested_fields
        for v in val:
            for field in fields_to_remove:
                v.pop(field)

        return val

    def find_one(self, entity_type, filters, fields=None, order=None, filter_operator=None, retired_only=False):
        results = self.find(entity_type, filters, fields=fields, order=order, filter_operator=filter_operator, retired_only=retired_only)
        return results[0] if results else None

    def batch(self, requests):
        results = []
        for request in requests:
            if request["request_type"] == "create":
                results.append(self.create(request["entity_type"], request["data"]))
            elif request["request_type"] == "update":
                # note: Shotgun.update returns a list of a single item
                results.append(self.update(request["entity_type"], request["entity_id"], request["data"])[0])
            elif request["request_type"] == "delete":
                results.append(self.delete(request["entity_type"], request["entity_id"]))
            else:
                raise ShotgunError("Invalid request type %s in request %s" % (request["request_type"], request))
        return results
    
    def _get_next_id(self, entity_type):
        try:
            # get next id in this table
            next_id = max(self._db[entity_type]) + 1
        except ValueError:
            next_id = 1
        return next_id

    def create(self, entity_type, data, return_fields=None):
        
        # special handling of storage fields - if a field value
        # is a dict with a key local_path, then add fields 
        # local_path_linux, local_path_windows, local_path_mac 
        # as a reflection of this
        for d in data:
            if isinstance(data[d], dict) and "local_path" in data[d]:
                # partly imitate some of the business logic happening on the 
                # server side of shotgun when a file/link entity value is created
                if "local_storage" not in data[d]:
                    data[d]["local_storage"] = {"id": 0, "name": "auto_generated_by_mockgun", "type": "LocalStorage"}
                if "local_path_linux" not in data[d]:
                    data[d]["local_path_linux"] = data[d]["local_path"]
                if "local_path_windows" not in data[d]:
                    data[d]["local_path_windows"] = data[d]["local_path"]
                if "local_path_mac" not in data[d]:
                    data[d]["local_path_mac"] = data[d]["local_path"]
        
        self._validate_entity_type(entity_type)
        self._validate_entity_data(entity_type, data)
        self._validate_entity_fields(entity_type, return_fields)

        row = self._get_new_row(entity_type)
        next_id = self._get_next_id(entity_type)
        row["id"] = next_id

        self._update_row(entity_type, row, data)

        # created_at can be set by a shotgun.create call, only set it automatically if not previously set.
        if row.get("created_at") is None:
            row["created_at"] = datetime.datetime.now()

        self._db[entity_type][next_id] = row

        # Create EventLogEntries
        if entity_type != 'EventLogEntry':  # prevent infinite loop
            self.create('EventLogEntry', {
                'event_type': 'Shotgun_{0}_New'.format(entity_type),
                'entity': {'type': entity_type, 'id': next_id},
                'meta': {'entity_id': next_id, 'entity_type': entity_type, 'type': 'new_entity'},
                # todo: add project
            })
            # {'attribute_name': None,
            # 'cached_display_name': None,
            # 'created_at': datetime.datetime(2017, 5, 16, 8, 26, 46, tzinfo=<tank_vendor.shotgun_api3.lib.sgtimezone.LocalTimezone object at 0x2d440d0>),
            # 'description': 'Gabrielle Gagnon created new Asset ',
            # 'entity': None,
            # 'event_type': 'Shotgun_Asset_New',
            # 'filmstrip_image': None,
            # 'id': 56534670,
            # 'image': None,
            # 'meta': {'entity_id': 4352, 'entity_type': 'Asset', 'type': 'new_entity'},
            # 'project': {'id': 339, 'name': 'Lynx-RushOfJustice', 'type': 'Project'},
            # 'session_uuid': 'dacd1664-3a32-11e7-97b8-0242ac110004',
            # 'type': 'EventLogEntry',
            # 'user': {'id': 152, 'name': 'Gabrielle Gagnon', 'type': 'HumanUser'}}

        if return_fields is None:
            result = dict((field, self._get_field_from_row(entity_type, row, field)) for field in data)
        else:
            result = dict((field, self._get_field_from_row(entity_type, row, field)) for field in return_fields)

        result["type"] = row["type"]
        result["id"] = row["id"]
        
        return result

    def update(self, entity_type, entity_id, data, multi_entity_update_modes=None):
        self._validate_entity_type(entity_type)
        self._validate_entity_data(entity_type, data)
        self._validate_entity_exists(entity_type, entity_id)

        row = self._db[entity_type][entity_id]
        self._update_row(entity_type, row, data, multi_entity_update_modes)

        return [dict((field, item) for field, item in row.items() if field in data or field in ("type", "id"))]

    def delete(self, entity_type, entity_id):
        self._validate_entity_type(entity_type)
        self._validate_entity_exists(entity_type, entity_id)
        
        row = self._db[entity_type][entity_id]
        if not row["__retired"]:
            row["__retired"] = True
            return True
        else:
            return False
    
    def revive(self, entity_type, entity_id):
        self._validate_entity_type(entity_type)
        self._validate_entity_exists(entity_type, entity_id)
        
        row = self._db[entity_type][entity_id]
        if row["__retired"]:
            row["__retired"] = False
            return True
        else:
            return False
    
    def upload(self, entity_type, entity_id, path, field_name=None, display_name=None, tag_list=None):
        raise NotImplementedError
    
    def upload_thumbnail(self, entity_type, entity_id, path, **kwargs):
        pass

    ###################################################################################################
    # internal methods and members

    def _validate_entity_type(self, entity_type):
        if entity_type not in self._schema:
            raise ShotgunError("%s is not a valid entity" % entity_type)
    
    def _validate_entity_data(self, entity_type, data):
        if "id" in data or "type" in data:
            raise ShotgunError("Can't set id or type on create or update")

        self._validate_entity_fields(entity_type, data.keys())

        for field, item in data.items():
            
            if item is None:
                # none is always ok
                continue
            
            field_info = self._schema[entity_type][field]

            if field_info["data_type"]["value"] == "multi_entity":
                if not isinstance(item, list):
                    raise ShotgunError("%s.%s is of type multi_entity, but data %s is not a list" % (entity_type, field, item))
                elif item and any(not isinstance(sub_item, dict) for sub_item in item):
                    raise ShotgunError("%s.%s is of type multi_entity, but data %s contains a non-dictionary" % (entity_type, field, item))
                elif item and any("id" not in sub_item or "type" not in sub_item for sub_item in item):
                    raise ShotgunError("%s.%s is of type multi-entity, but an item in data %s does not contain 'type' and 'id'" % (entity_type, field, item))
                elif item and any(sub_item["type"] not in field_info["properties"]["valid_types"]["value"] for sub_item in item):
                    raise ShotgunError("%s.%s is of multi-type entity, but an item in data %s has an invalid type (expected one of %s)" % (entity_type, field, item, field_info["properties"]["valid_types"]["value"]))
                
                
            elif field_info["data_type"]["value"] == "entity":
                if not isinstance(item, dict):
                    raise ShotgunError("%s.%s is of type entity, but data %s is not a dictionary" % (entity_type, field, item))
                elif "id" not in item or "type" not in item:
                    raise ShotgunError("%s.%s is of type entity, but data %s does not contain 'type' and 'id'" % (entity_type, field, item))
                #elif item["type"] not in field_info["properties"]["valid_types"]["value"]:
                #    raise ShotgunError("%s.%s is of type entity, but data %s has an invalid type (expected one of %s)" % (entity_type, field, item, field_info["properties"]["valid_types"]["value"]))

            else:
                try:
                    sg_type = field_info["data_type"]["value"]
                    python_type = {"number": int,
                                   "float": float,
                                   "checkbox": bool,
                                   "percent": int,
                                   "text": basestring,
                                   "serializable": dict,
                                   "date": datetime.date,
                                   "date_time": datetime.datetime,
                                   "list": basestring,
                                   "status_list": basestring,
                                   "color": basestring,
                                   "url": dict}[sg_type]
                except KeyError:
                    raise ShotgunError("Field %s.%s: Handling for Shotgun type %s is not implemented" % (entity_type, field, sg_type)) 
                
                if not isinstance(item, python_type):
                    raise ShotgunError("%s.%s is of type %s, but data %s is not of type %s" % (entity_type, field, type(item), sg_type, python_type))

                # TODO: add check for correct timezone

    def _validate_entity_fields(self, entity_type, fields):
        self._validate_entity_type(entity_type)
        if fields is not None:
            valid_fields = set(self._schema[entity_type].keys())
            for field in fields:
                try:
                    field2, entity_type2, field3 = field.split(".", 2)
                    self._validate_entity_fields(entity_type2, [field3])
                except ValueError:
                    if field not in valid_fields and field not in ("type", "id"):
                        raise ShotgunError("%s is not a valid field for entity %s" % (field, entity_type))

    def _get_default_value(self, entity_type, field):
        field_info = self._schema[entity_type][field]
        if field_info["data_type"]["value"] == "multi_entity":
            default_value = []
        else:
            default_value = field_info["properties"]["default_value"]["value"]
        return default_value

    def _get_new_row(self, entity_type):
        row = {"type": entity_type, "__retired": False}
        for field in self._schema[entity_type]:
            field_info = self._schema[entity_type][field]
            if field_info["data_type"]["value"] == "multi_entity":
                default_value = []
            else:
                default_value = field_info["properties"]["default_value"]["value"]
            row[field] = default_value
        return row

    def _compare(self, field_type, lval, operator, rval):
        """
        Compares a field using the operator and value provide by the filter.

        :param str field_type: Type of the field we are operating on.
        :param lval: Value inside that field. Can be of any type: datetime, date, int, str, bool, etc.
        :param str operator: Name of the operator to use.
        :param rval: The value following the operator in a filter.

        :returns: The result of the operator that was applied.
        :rtype: bool
        """
        # If we have a list of scalar values
        if isinstance(lval, list) and field_type != "multi_entity":
            # If the list is empty, the return value will depend if we are checking for None or not.
            if not lval:
                return self._compare(field_type, None, operator, rval)

            # Compare each one. If one matches the predicate we're good!
            return any((self._compare(field_type, sub_val, operator, rval)) for sub_val in lval)

        if field_type == "checkbox":
            if operator == "is":
                return lval == rval
            elif operator == "is_not":
                return lval != rval
        elif field_type in ("float", "number", "date", "date_time"):
            if operator == "is":
                return lval == rval
            elif operator == "is_not":
                return lval != rval
            elif operator == "less_than":
                return lval < rval
            elif operator == "greater_than":
                return lval > rval
            elif operator == "between":
                return lval >= rval[0] and lval <= rval[1]
            elif operator == "not_between":
                return lval < rval[0] or lval > rval[1]
            elif operator == "in":
                return lval in rval
        elif field_type in ("list", "status_list"):
            if operator == "is":
                return lval == rval
            elif operator == "is_not":
                return lval != rval
            elif operator == "in":
                return rval and lval in rval  # rval might be None
            elif operator == "not_in":
                return not rval or lval not in rval  # rval might be None
        elif field_type == "entity_type":
            if operator == "is":
                return lval == rval
        elif field_type == "text":
            if operator == "is":
                return lval == rval
            elif operator == "is_not":
                return lval != rval
            elif operator == "in":
                return rval and lval in rval  # rval might be None
            elif operator == "contains":
                return lval and rval in lval  # lval might be None
            elif operator == "not_contains":
                return not lval or lval not in rval  # lval might be None
            elif operator == "starts_with":
                return lval.startswith(rval)
            elif operator == "ends_with":
                return lval.endswith(rval)
        elif field_type == "entity":
            if operator == "is":
                # If one of the two is None, ensure both are.
                if lval is None or rval is None:
                    return lval == rval
                # Both values are set, compare them.
                return lval["type"] == rval["type"] and lval["id"] == rval["id"]
            elif operator == "is_not":
                if lval is None or rval is None:
                    return lval != rval
                if rval is None:
                    # We already know lval is not None, so we know they are not equal.
                    return True
                return lval["type"] != rval["type"] or lval["id"] != rval["id"]
            elif operator == "in":
                return all((lval["type"] == sub_rval["type"] and lval["id"] == sub_rval["id"]) for sub_rval in rval)
            elif operator == "type_is":
                return lval["type"] == rval
            elif operator == "type_is_not":
                return lval["type"] != rval
            elif operator == "name_contains":
                return rval in lval["name"]
            elif operator == "name_not_contains":
                return rval not in lval["name"]
            elif operator == "name_starts_with":
                return lval["name"].startswith(rval)
            elif operator == "name_ends_with":
                return lval["name"].endswith(rval)
        elif field_type == "multi_entity":
            if operator == "is":
                if rval is None:
                    return len(lval) == 0
                return rval["id"] in (sub_lval["id"] for sub_lval in lval)
            elif operator == "is_not":
                if rval is None:
                    return len(lval) != 0
                return rval["id"] not in (sub_lval["id"] for sub_lval in lval)

        raise ShotgunError("The %s operator is not supported on the %s type" % (operator, field_type))

    def _get_field_from_row(self, entity_type, row, field):
        # split dotted form fields
        try:
            # is it something like sg_sequence.Sequence.code ?
            field2, entity_type2, field3 = field.split(".", 2)

            if field2 in row:

                field_value = row[field2]

                # If we have a list of links, retrieve the subfields one by one.
                if isinstance(field_value, list):
                    values = []
                    for linked_row in field_value:
                        # Make sure we're actually iterating on links.
                        if not isinstance(linked_row, dict):
                            raise ShotgunError("Invalid deep query field %s.%s" % (entity_type, field))

                        # Skips entities that are not of the requested type.
                        if linked_row["type"] != entity_type2:
                            continue

                        entity = self._db[linked_row["type"]][linked_row["id"]]

                        sub_field_value = self._get_field_from_row(entity_type2, entity, field3)
                        values.append(sub_field_value)
                    return values
                elif field_value is None:
                    return None
                # not multi entity, must be entity.
                elif not isinstance(field_value, dict):
                    raise ShotgunError("Invalid deep query field %s.%s" % (entity_type, field))

                # ok so looks like the value is an entity link
                # e.g. db contains: {"sg_sequence": {"type":"Sequence", "id": 123 } }
                linked_row = self._db[ field_value["type"] ][ field_value["id"] ]

                return self._get_field_from_row(entity_type2, linked_row, field3)
            else:
                # sg returns none for unknown stuff
                return None

        except ValueError:
            # this is not a deep-linked field - just something like "code"
            if field in row:
                return row[field]
            else:
                # sg returns none for unknown stuff
                return None

    def _handle_name_field(self, val):
        """
        Inject the 'name' field if missing.
        This is used to reproduce the default shotgun behavior when returning entity fields from find().
        Example:
        >>> sg.find_one('Task', [['project', 'is_not', None]], ['project'])
        {'project': {'type': 'Project', 'id': 65, 'name': 'Demo Animation Project'}, 'type': 'Task', 'id': 156}
        """
        # Here are the fields that can be used to create the 'name' field
        source_field_names = (
            'name',  # ex: Project entity
            'code',  # ex: Shot entity
            'content',  # ex: Task entity
        )

        if isinstance(val, list):  # list of entity
            return [self._handle_name_field(item) for item in val]
        elif isinstance(val, dict) and "type" in val and "id" in val:  # entity
            if "name" not in val:
                entity_type = val["type"]
                entity_id = val["id"]

                val = copy.copy(val)  # ensure we do not modify the database by accident
                row = self._db[entity_type][entity_id]

                # Resolve the value associated with the field
                for field_name in source_field_names:
                    try:
                        field_value = row[field_name]
                    except LookupError:
                        continue
                    val["name"] = field_value
                    break

                if "name" not in val:
                    raise ShotgunError("Cannot resolve name field from {0} #{1}: {2}".format(
                        entity_type, entity_id, row
                    ))
            return val
        else:
            return val

    def _get_field_type(self, entity_type, field):
        # The 'id' field is not included in the schema???
        if field == 'id':
            return 'number'
        # split dotted form fields
        try:
            field2, entity_type2, field3 = field.split(".", 2)
            return self._get_field_type(entity_type2, field3)
        except ValueError:
            return self._schema[entity_type][field]["data_type"]["value"]

    def _row_matches_filter(self, entity_type, row, sg_filter, retired_only):

        try:
            field, operator, rval = sg_filter
        except ValueError:
            raise ShotgunError("Filters must be in the form [lval, operator, rval]")

        # Special case, field is None when we have a filter operator.
        if field is None:
            if operator in ["any", "all"]:
                return self._row_matches_filters(entity_type, row, rval, operator, retired_only)
            else:
                raise ShotgunError("Unknown filter_operator type: %s" % operator)
        else:

            lval = self._get_field_from_row(entity_type, row, field)

            field_type = self._get_field_type(entity_type, field)

            # if we're operating on an entity, we'll need to grab the name from the lval's row
            if field_type == "entity":
                # If the entity field is set, we'll retrieve the name of the entity.
                if lval is not None:
                    link_type = lval["type"]
                    link_id = lval["id"]
                    lval_row = self._db[link_type][link_id]
                    if "name" in lval_row:
                        lval["name"] = lval_row["name"]
                    elif "code" in lval_row:
                        lval["name"] = lval_row["code"]

            return self._compare(field_type, lval, operator, rval)

    def _rearrange_filters(self, filters):
        """
        Modifies the filter syntax to turn it into a list of three items regardless
        of the actual filter. Most of the filters are list of three elements, so this doesn't change much.

        The filter_operator syntax uses a dictionary with two keys, "filters" and
        "filter_operator". Filters using this syntax will be turned into
        [None, filter["filter_operator"], filter["filters"]]

        Filters of the form [field, operator, values....] will be turned into
        [field, operator, [values...]].

        :param list filters: List of filters to rearrange.

        :returns: A list of three items.
        """
        rearranged_filters = []

        # now translate ["field", "in", 2,3,4] --> ["field", "in", [2, 3, 4]]
        for f in filters:
            if isinstance(f, list):
                if len(f) > 3:
                    # ["field", "in", 2,3,4] --> ["field", "in", [2, 3, 4]]
                    new_filter = [f[0], f[1], f[2:]]

                elif f[1] == "in" and not isinstance(f[2], list):
                    # ["field", "in", 2] --> ["field", "in", [2]]
                    new_filter = [f[0], f[1], [f[2]]]

                else:
                    new_filter = f
            elif isinstance(f, dict):
                if "filter_operator" not in f or "filters" not in f:
                    raise ShotgunError(
                        "Bad filter operator, requires keys 'filter_operator' and 'filters', "
                        "found %s" % ", ".join(f.keys())
                    )
                new_filter = [None, f["filter_operator"], f["filters"]]
            else:
                raise ShotgunError(
                    "Filters can only be lists or dictionaries, not %s." % type(f).__name__
                )

            rearranged_filters.append(new_filter)

        return rearranged_filters

    def _row_matches_filters(self, entity_type, row, filters, filter_operator, retired_only):
        filters = self._rearrange_filters(filters)

        if retired_only and not row["__retired"] or not retired_only and row["__retired"]:
            # ignore retired rows unless the retired_only flag is set
            # ignore live rows if the retired_only flag is set
            return False
        elif filter_operator in ("all", None):
            return all(self._row_matches_filter(entity_type, row, filter, retired_only) for filter in filters)
        elif filter_operator == "any":
            return any(self._row_matches_filter(entity_type, row, filter, retired_only) for filter in filters)
        else:
            raise ShotgunError("%s is not a valid filter operator" % filter_operator)

    def _create_event_attribute_change(self, entity, attr_name, old_val, new_val):
        # {'attribute_name': 'color',
        #  'cached_display_name': None,
        #  'created_at': datetime.datetime(2017, 5, 16, 8, 25, 3, tzinfo=<tank_vendor.shotgun_api3.lib.sgtimezone.LocalTimezone object at 0x210f050>),
        #  'description': 'Gabrielle Gagnon changed "Gantt Bar Color" from "" to "pipeline_step" on Task LegoDirecting',
        #  'entity': None,
        #  'event_type': 'Shotgun_Task_Change',
        #  'filmstrip_image': None,
        #  'id': 56534551,
        #  'image': None,
        #  'meta': {'attribute_name': 'color',
        #           'entity_id': 73747,
        #           'entity_type': 'Task',
        #           'field_data_type': 'color',
        #           'in_create': True,
        #           'new_value': 'pipeline_step',
        #           'old_value': None,
        #           'type': 'attribute_change'},
        #  'project': {'id': 342, 'name': 'Lego-LegoCity', 'type': 'Project'},
        #  'session_uuid': '94a8057c-3a32-11e7-97b8-0242ac110004',
        #  'type': 'EventLogEntry',
        #  'user': {'id': 152, 'name': 'Gabrielle Gagnon', 'type': 'HumanUser'}}

        self.create('EventLogEntry', {
            'attribute_name': attr_name,
            # 'description': '{0} changed "{1}" from "{2}" to "{3}" on {4} {5}'.format(
            #     'MockedUser', attr_name, old_val, new_val, entity['type'], entity['name']
            # ),
            'entity': {'type': entity['type'], 'id': entity['id']},
            'event_type': 'Shotgun_{0}_Change'.format(entity['type']),
            'meta': {
                'attribute_name': attr_name,
                'entity_id': entity['id'],
                'entity_type': entity['type'],
                # 'field_data_type': # todo
                # 'in_create':  # todo
                'new_value': new_val,
                'old_value': old_val,
                'type': 'attribute_change'
            },
            # 'project': # todo
            'user': self._current_user,
        })

    def _is_entity_in_list(self, entity, list_):
        """
        Utility method that check if an entity is in a multi-entity list.
        It only check the type and id, which is useful if we have other fields like 'name' in our values.
        """
        for entry in list_:
            if entry["type"] == entity["type"] and entry["id"] == entity["id"]:
                return True
        return False

    def _update_row(self, entity_type, row, data, multi_entity_update_modes=None):
        for field in data:
            field_type = self._get_field_type(entity_type, field)
            old_val = row[field]
            if field_type == "entity" and data[field]:
                new_val = {"type": data[field]["type"], "id": data[field]["id"]}
            elif field_type == "multi_entity":
                update_mode = multi_entity_update_modes.get(entity_type, "set") if multi_entity_update_modes is not None else "set"
                if update_mode == 'set':
                    new_val = [{"type": item["type"], "id": item["id"]} for item in data[field]]
                elif update_mode == 'add':
                    new_val = copy.copy(row[field])
                    for item in data[field]:
                        if not self._is_entity_in_list(item, new_val):
                            new_val.append({"type": item["type"], "id": item["id"]})
                elif update_mode == "remove":
                    entities_to_remove = data[field]
                    new_val = [item for item in row[field] if not self._is_entity_in_list(item, entities_to_remove)]
                else:
                    raise Exception("Unsupported update_mode {0}".format(update_mode))
            else:
                new_val = data[field]
            row[field] = new_val
            if entity_type != 'EventLogEntry':
                self._create_event_attribute_change(row, field, old_val, new_val)

    def _validate_entity_exists(self, entity_type, entity_id):
        if entity_id not in self._db[entity_type]:
            raise ShotgunError("No entity of type %s exists with id %s" % (entity_type, entity_id))
