import matplotlib.pyplot as plt
from .utils import write_to_file_field

def get_map_figure_size(extent, height=8.):
    width = height / (extent[3] - extent[1]) * (extent[2] - extent[0])
    return [width + 1, height]

def plot_map(raster, file_field=None):
    plt.figure(figsize=get_map_figure_size(ci.bounds))
    ax, mapimg = raster.plotmap(  # ax=ax,
        cmap='jet',
        logcolor=True,
        legend=True,
        # maptype='minimal',
        grid=True, gridrange=1,
        vmax=ceamaxval)

    ax.add_image(cimgt.Stamen('toner-lite'), get_zoomlevel(ci.geobounds))
    if file_field is not None:
        write_to_file_field(file_field, plt.savefig, 'png')
        plt.clf()
        plt.close()


