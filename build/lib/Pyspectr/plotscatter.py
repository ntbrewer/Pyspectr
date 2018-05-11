def plotscatter(plotobj):
    import matplotlib.pyplot as plt
    import numpy as np
    plt.subplots(1)
    arr=plotobj.histogram.weights.nonzero()
    y=arr[1]
    x=arr[0]
    cc = plotobj.histogram.weights[x,y]

    plt.scatter(x,y,s=50, c=cc)
    plt.legend()
    plt.show()

