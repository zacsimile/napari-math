from typing import Optional
from napari.layers import Layer, Points, Surface, Image
from napari.types import LayerDataTuple
from napari.utils._magicgui import find_viewer_ancestor

from magicgui import magic_factory
from magicgui.widgets import FunctionGui
import numpy as np



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


def math_init(widget: FunctionGui):
    @widget.layer0.changed.connect
    def _layer0_callback(new_layer: Layer):
        widget.layer1.reset_choices()
        widget.layer1.visible = isinstance(new_layer, Image)

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


def _l1choices(wdg):
    layers = []
    parent = wdg.parent
    if parent:
        # hi onlooker, avert your eyes, this is awful and should not be emulated :)
        math_widget = None
        while parent:
            # look for the parent math_widget FunctionGui
            if isinstance(getattr(parent, '_magic_widget', None), FunctionGui):
                math_widget = parent._magic_widget
                break
            parent = parent.parent()
        assert math_widget, 'Could not find parent FunctionGui?'

        lay0 = math_widget.layer0.value
        viewer = find_viewer_ancestor(math_widget)
        if viewer and isinstance(lay0, Image):
            layers.extend([x for x in viewer.layers if isinstance(x, type(lay0))])
            # TODO: deal with other layer types
    return layers


@magic_factory(
    widget_init=math_init,
    operation={"choices": operation_dict.keys()},
    layer1={"choices": _l1choices, "nullable": True},
    _lbl={'widget_type': 'Label'},
    layout="horizontal",
    labels=False,
    call_button="Calculate",
)
def make_math_widget(layer0: Layer,
                     operation: str,
                     _lbl = '  x',
                     scalar: float = 1.0,
                     layer1: Optional[Layer] = None) -> LayerDataTuple:

    # Store source images in metadata
    layer0_name = layer0._source.path if layer0._source.path is not None else layer0.name
    md = {"layer0": layer0_name, "operation": operation, "scalar": scalar}

    if layer1:
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
