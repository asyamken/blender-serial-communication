
import bpy
import serial
import serial.tools.list_ports
from bpy.props import (StringProperty, 
                       IntProperty, 
                       FloatProperty, 
                       PointerProperty, 
                       CollectionProperty, 
                       EnumProperty)
from bpy.types import (Panel, 
                       Operator, 
                       PropertyGroup)
                       
class SinglePortStruct(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(SinglePortStruct, cls).__new__(cls)
        return cls.instance
    

def get_current_ports():
    portStruct = SinglePortStruct()
    ports = serial.tools.list_ports.comports(include_links=False)
    for port in ports :
        print('Find port '+ port.device)
    if not hasattr(portStruct, 'port_list'): 
        portStruct.port_list = ports
    else: 
        try: 
            portStruct.correct_port = list(set(ports)-set(portStruct.port_list))[0]
            print(portStruct.correct_port.device)
        except IndexError: 
            return

def fill_items(context):
    items = []
    node = context.active_object.active_material.node_tree.nodes.active
    if node:
        for socket in node.inputs:
            if socket.type == 'VALUE' and socket.enabled:
                items.append((f"{socket.name} - {socket.node.name}", f"{socket.name}", "Input"))
        for socket in node.outputs:
            if socket.type == 'VALUE' and socket.enabled:
                items.append((f"{socket.name} - {socket.node.name}", f"{socket.name}", "Output"))
    return items

def calculate_new_value(entry, value): 
    smin = entry.sensor_value_min
    smax = entry.sensor_value_max 
    nmin = entry.node_value_min 
    nmax = entry.node_value_max 
    partition = (((value-smin)/(smax-smin))*(nmax-nmin))
    return partition+nmin


# ------------------------------------------------------------------------
#    Object Properties
# ------------------------------------------------------------------------ 

class SensorProperties(PropertyGroup):
    sensor_label: StringProperty(name="Sensor Label", default="")
    node_value_min: FloatProperty(name="Node Min", default=0.0)
    node_value_max: FloatProperty(name="Node Max", default=1.0)
    sensor_value_min: FloatProperty(name="Sensor Min", default=0.0)
    sensor_value_max: FloatProperty(name="Sensor Max", default=100.0)

class PanelProperties(PropertyGroup):
    sensor_slider: IntProperty(name="Num of Sensors", default=1, min=0)
    sensor_collection: CollectionProperty(type=SensorProperties)
    node_value_list: EnumProperty(name="Node Value", items=lambda self, context: fill_items(context))
    connection_label: StringProperty(name="Connection Status", default="Connect")


class OBJECT_OT_AddSensor(Operator):
    bl_idname = "object.add_sensor"
    bl_label = "Add Sensor"
    bl_description = "Add a new sensor to the list"

    def execute(self, context):
        sensorTool = context.object.sensor_tool
        labels = []
        for sensor in sensorTool.sensor_collection: 
            labels.append(sensor.sensor_label)
            
        if len(sensorTool.sensor_collection) < sensorTool.sensor_slider:
            selected_value = sensorTool.node_value_list
            if selected_value not in labels:
                sensor = sensorTool.sensor_collection.add()
                
                sensor.sensor_label = selected_value if selected_value else f"Sensor {len(sensorTool.sensor_collection) + 1}"
            else: 
                self.report({'WARNING'}, "Sensor already exists")
        else:
            self.report({'WARNING'}, "Maximum number of sensors reached.")
        return {'FINISHED'}

class OBJECT_OT_RemoveSensor(Operator):
    bl_idname = "object.remove_sensor"
    bl_label = "Remove Sensor"
    bl_description = "Remove the last sensor from the list"

    def execute(self, context):
        sensorTool = context.object.sensor_tool
        if sensorTool.sensor_collection:
            sensorTool.sensor_collection.remove(len(sensorTool.sensor_collection) - 1)
        return {'FINISHED'}
    
class OBJECT_OT_unregister(Operator):
    bl_idname = "object.unregister"
    bl_label = "Close/Disconnect"
    bl_description = "unregister panel"

    def execute(self, context):
        portStruct = SinglePortStruct()
        if hasattr(portStruct, 'serial'):
            portStruct.serial.close()
        sensorTool = context.object.sensor_tool
        # Reset properties
        sensorTool.sensor_slider = 1
        sensorTool.selected_labels = ""
        sensorTool.sensor_collection.clear()
        sensorTool.connection_label = "Connect"
        unregister()
        print("unregistering everything")
        return {'FINISHED'} 
    
class OBJECT_OT_connect(Operator):
    bl_idname = "object.connect"
    bl_label = "Connect"
    bl_description = "connector button"    

    def execute(self, context):
        self.report({'INFO'}, "Connection initiating")
        get_current_ports()
        
        sensorTool = context.object.sensor_tool
        
        portStruct = SinglePortStruct()
        if hasattr(portStruct, 'correct_port'): 
            try:
                portStruct.serial = serial.Serial(portStruct.correct_port.device, 115200, timeout=1)
                sensorTool.connection_label = f"Connected to {portStruct.serial.name}"
                self.report({'INFO'}, sensorTool.connection_label)
            except Exception:
                self.report({'WARNING'}, "Something went wrong, please try again")
        else: 
            self.report({'WARNING'}, "Couldn't find controller")
        
        return {'FINISHED'}

class OBJECT_OT_update_data(Operator):
    bl_idname = "object.update_data"
    bl_label = "Update sensor data"
    bl_description = "update button"    

    def execute(self, context):
        port = SinglePortStruct()
        sensorTool = context.object.sensor_tool 
        if hasattr(port, 'serial'):
            ser = port.serial
            ser.write(b'Get All\n')
            result = ser.readline()
            if result != b'':
                try: 
                    vals = result.decode('ascii').replace("|\r\n",'').split(',')
                    vals = [float(i) for i in vals]
                    print(vals)
                    if len(sensorTool.sensor_collection) != 0:
                        if len(vals) != len(sensorTool.sensor_collection):
                            if len(vals) > len(sensorTool.sensor_collection):
                                self.report({'INFO'}, f"Received more values than targets. Only first {len(sensorTool.sensor_collection)} values will be applied")
                                changes = len(sensorTool.sensor_collection)
                            elif len(vals) < len(sensorTool.sensor_collection): 
                                self.report({'INFO'}, f"Received less values than targets. Values will only be applied to first {len(vals)} targets")
                                changes = len(vals)
                        else: 
                            changes = len(vals)
                    else: 
                        self.report({'WARNING'}, "No targets found")
                        return {'FINISHED'}
                    for i in range(changes):
                        entry = sensorTool.sensor_collection[i]
                        if int(vals[i]) not in range(int(entry.sensor_value_min)-1,int(entry.sensor_value_max)+1): 
                            print(vals[i] not in range(int(entry.sensor_value_min),int(entry.sensor_value_max)))
                            print(range(int(entry.sensor_value_min),int(entry.sensor_value_max)))
                            self.report({'INFO'}, f"Value out of bounds for {entry.sensor_label} ({vals[i]})")
                            continue
                        target,parent = entry.sensor_label.split(' - ')
                        try: 
                            node = context.object.active_material.node_tree.nodes[parent].inputs[target]
                        except KeyError: 
                            try:
                                node = context.object.active_material.node_tree.nodes[parent].outputs[target]
                            except KeyError:
                                self.report({'WARNING'}, f"Node {parent} or input/output {target} not found!")
                                continue  # Skip this entry
                        node.default_value = calculate_new_value(entry, vals[i])
                except ValueError:
                    self.report({'WARNING'}, "Didn't receive proper data, please try again")
            else: 
                self.report({'WARNING'}, "Didn't receive any data, please try again")
        else: 
            self.report({'WARNING'},"No controller connected!")
        return {'FINISHED'}

# ------------------------------------------------------------------------
#    Panel in Object Mode
# ------------------------------------------------------------------------

class OBJECT_PT_SensorPanel(Panel):
    bl_label = "Sensor Control Tool"
    bl_idname = "NODE_PT_custom_panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Sensors"

    @classmethod
    def poll(cls, context):
        return context.object is not None
    
    def draw(self, context):
        layout = self.layout
        sensorTool = context.object.sensor_tool
        
        layout.operator(OBJECT_OT_connect.bl_idname, text=sensorTool.connection_label)
        layout.separator()
        
        # Slider for number of sensors
        layout.prop(sensorTool, "sensor_slider")
        
        # Node Value Dropdown
        layout.prop(sensorTool, "node_value_list")
        
        # Add and Remove Sensor Buttons
        layout.operator(OBJECT_OT_AddSensor.bl_idname)
        layout.operator(OBJECT_OT_RemoveSensor.bl_idname)
        
        # Display current sensors and their values
        for i, sensor in enumerate(sensorTool.sensor_collection):
            layout.label(text=sensor.sensor_label)
            layout.prop(sensor, "node_value_min")
            layout.prop(sensor, "node_value_max")
            layout.prop(sensor, "sensor_value_min")
            layout.prop(sensor, "sensor_value_max")
            
        layout.separator()
        layout.operator(OBJECT_OT_update_data.bl_idname)
        
        layout.separator()
        layout.operator(OBJECT_OT_unregister.bl_idname)

# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    SensorProperties,
    PanelProperties,
    OBJECT_PT_SensorPanel,
    OBJECT_OT_AddSensor,
    OBJECT_OT_RemoveSensor,
    OBJECT_OT_unregister,
    OBJECT_OT_connect,
    OBJECT_OT_update_data,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    
    bpy.types.Object.sensor_tool = PointerProperty(type=PanelProperties)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Object.sensor_tool

if __name__ == "__main__":
    get_current_ports()
    register()
