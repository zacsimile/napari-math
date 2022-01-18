from xxlimited import new
from napari.layers import Layer, Points, Surface, Image
from napari.types import LayerDataTuple
from napari.utils._magicgui import find_viewer_ancestor

from magicgui import magic_factory
import numpy as np
from enum import Enum

# set of all possible operations
operation_dict = {'add': np.add,
                  'subtract': np.subtract,
                  'multiply': np.multiply,
                  'divide': np.divide,
                  'and': np.logical_and,
                  'or': np.logical_or,
                  'xor': np.logical_xor,
                  'z-project sum' : lambda x, y: np.sum(x,axis=2),
                  'z-project mean' : lambda x, y: np.mean(x,axis=2)}

def get_layer_data(layer):
    # Return a single numpy array to manipulate
    # for each layer type (only grab the vertices
    # of a surface)
    if type(layer) == Surface:
        try:
            v, _, _ = layer.data
        except ValueError :
            v, _ = layer.data
        return v
    else:
        return layer.data

def math_init(widget):
    @widget.layer0.changed.connect
    def _layer0_callback(new_layer: Layer):
        viewer = find_viewer_ancestor(widget)
        layers = ["<no layer>"]
        # Update layers
        if type(new_layer) == Image:
            for layer in viewer.layers:
                if type(layer) == Image:
                    layers.append(layer)
            widget.layer1.visible = True
        else:
            widget.layer1.visible = False
        widget.layer1.choices = layers

        # Update operations
        opts = ['add', 'subtract', 'multiply', 'divide']
        if type(new_layer) == Image:
            opts.extend(['and', 'or', 'xor', 'z-project sum', 'z-project mean'])
        widget.operation.choices = opts

    @widget.operation.changed.connect
    def _operation_callback(new_operation: str):
        if new_operation.startswith('z-project'):
            widget.scalar.visible = False
            widget.layer1.visible = False
        else:
            widget.scalar.visible = True
            widget.layer1.visible = True

    @widget.layer1.changed.connect
    def _layer1_callback(new_layer: Layer):
        if ((type(widget.layer0) == Surface) and (type(widget.layer1) == Points)) \
           or ((type(widget.layer0) == Points) and (type(widget.layer1) == Surface)):
           widget.operation.choices = ['and']            

@magic_factory(widget_init=math_init, layer0={'label' : '\u0020'},
               operation={'choices' : list(operation_dict.keys()), 'label' : '\u0020'},
               scalar={'label' : '\u0020'}, layer1={'choices': ["<no layer>"], 'label': ' x '},
               layout='horizontal', call_button='Calculate',)
def make_math_widget(layer0: Layer, 
                     operation: str, 
                     scalar: float = 1.0, 
                     layer1: Layer = "<no layer>") -> LayerDataTuple:

    # Store source images in metadata
    layer0_name = layer0._source.path if layer0._source.path is not None else layer0.name
    md = {"layer0": layer0_name, "operation": operation, "scalar": scalar}

    if layer1 == "<no layer>":
        # If we're only dealing with one layer, we only need to apply the operation
        # to the scalar
        data = operation_dict.get(operation)(get_layer_data(layer0).T, scalar).T
        if type(layer0) == Surface:
            c = None
            try:
                v, f, c = layer0.data
            except ValueError :
                v, c = layer0.data
            if c is None:
                data = (data, f)
            else:
                data = (data, f, c)
    else:
        # Store metadata
        md["layer1"] = layer1._source.path if layer1._source.path is not None else layer1.name

        # Grab the layer data
        data0 = get_layer_data(layer0)
        data1 = get_layer_data(layer1)

        tl0, tl1 = type(layer0), type(layer1)

        # If the layer data shapes match, we can apply any operation directly
        if data0.shape == data1.shape:
            data = operation_dict.get(operation)(data0.T, scalar*data1.T).T
        elif (tl0 == Image) and (tl1 == Image):
            # Image / Image, not the same shape
            # clip to minimum of the two images
            
            # Get bounds
            ld0, ld1 = len(data0.T.shape), len(data1.T.shape)
            l, u = min(ld0, ld1), max(ld0, ld1)
           
            # Construct slices for larger and smaller image
            sh = tuple([slice(0, min(data0.T.shape[i],data1.T.shape[i])) for i in range(l)])
            shu = sh + tuple([slice(0, 1) for i in range(u-l)])
            
            if ld0 < ld1:
                data = operation_dict.get(operation)(data0.T[sh].squeeze(), scalar*data1.T[shu].squeeze()).T
            else:
                data = operation_dict.get(operation)(data0.T[shu].squeeze(), scalar*data1.T[sh].squeeze()).T
        else:
            raise NotImplementedError(f"There is currently no support for {operation} on {tl0} and {tl1}.")

        # For TODOs, treat surface as a signed distance field when intersecting with other layer types?
        
        # TODO: Image / Surface (Surface / Image)
        # TODO: Surface / Points (Points / Surface)
        # TODO: Image / Points (Points / Image)
        # TODO: Surface / Surface
        # TODO: Points / Points

    # By default we return a new layer of type layer0
    return [(data, {"metadata": md}, layer0._type_string)]
