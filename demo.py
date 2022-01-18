import napari
from napari_math import make_math_widget

viewer = napari.Viewer()
viewer.open_sample('napari', 'cells3d')

widget = make_math_widget()
viewer.window.add_dock_widget(widget, area='bottom')
napari.run()
