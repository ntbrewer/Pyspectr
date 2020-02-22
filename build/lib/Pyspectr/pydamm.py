#!/usr/bin/env python3
"""K. Miernik 2012
k.a.miernik@gmail.com
Distributed under GNU General Public Licence v3

This module is inteded to be loaded in an interactive interpreter session.
The ipython is strongly recommended. The pydamm is a python replacement for
DAMM programm.

"""

import math
import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import re

from collections import deque

from Pyspectr import hisfile as hisfile
from Pyspectr import histogram as histogram
from Pyspectr import plotter as plotter
from Pyspectr.exceptions import GeneralError as GeneralError
from Pyspectr.decay_fitter import DecayFitter as DecayFitter
from Pyspectr.peak_fitter import PeakFitter as PeakFitter


class Plot:
    """
    The Plot class holds a set of data and parameters that are needed to
    display the data. 

    The bin_size attribute defines how much the histogram should be binned
    The norm attribute defines the normalization parameter used

    These parameters are altering the display only, the histogram 
    always keeps the original data.

    If the binned or normalized histogram data are needed for direct
    access, use functions avaible in the Histogram class.

    The mode defines the way the data are presented,
    'histogram' is displayed with steps-mid
    'function' with continuus line
    'errorbar' with yerrorbars
    'map' for 2D histograms

    """

    def __init__(self, histogram, mode, active):
        self.histogram = histogram
        self.mode = mode
        self.active = active

        self._bin_size = 1
        self._norm = 1


    @property
    def bin_size(self):
        return self._bin_size


    @bin_size.setter
    def bin_size(self, bs):
        if self.histogram.dim != 1:
            raise GeneralError('Currently only 1D histograms can be binned')

        if isinstance(bs, int):
            # You can only bin further the histogram, there is no
            # way back (load original data again)
            if bs > self._bin_size:
                self._bin_size = bs
                self.histogram = self.histogram.rebin1d(bs)
            elif bs <= self._bin_size:
                pass
            else:
                raise GeneralError('Attempt to set bin size to {}'.\
                        format(bs))
        else:
            raise GeneralError('Attempt to set bin size to {}'.\
                    format(bs))


    @property
    def norm(self):
        return self._norm


    @norm.setter
    def norm(self, n):
        if self.histogram.dim != 1:
            raise GeneralError('Currently only 1D histograms can be normalized')
        self.histogram = self.histogram.normalize1d(n, self.bin_size)



    def __str__(self):
        """Basic information Informative string"""
        string = 'Plot: {} bin {} norm {:.2e} sum {}'.\
                    format(self.histogram.title.strip(), self.bin_size,
                           self.norm, self.histogram.weights.sum())
        return string


    def __repr__(self):
        """More verbose string

        """
        #string = 'Plot: "{}" bin {} norm {:.2e} active {} mode {} sum {}'.\
        #            format(self.histogram.title.strip(), self.bin_size,
        #                   self.norm, self.active, self.mode, self.histogram.weights.sum())
        string = 'Plot: {} '.format(self.histogram.title.strip())
        return string



class Experiment:
    """Main class for data visualization and analysis

    """
    # Deque lengths
    FIFO_1D = 50
    FIFO_2D = 5

    # These variables and registers are class wide, so
    # if more than one Experiment is open (one file = one Experiment)
    # they share the registers and auto-scaling is still working

    # Keeps current and past 1D plots
    # The right-most item is the current one
    plots = deque(maxlen=FIFO_1D)

    # Current and past 2D plots
    maps = deque(maxlen=FIFO_2D)

    # 1D plot ranges
    xlim = None
    ylim = None

    # 2D plot ranges
    xlim2d = None
    ylim2d = None
    logz = False #For 2d histograms
    logy = False #For 1d histograms

    # 1 for 1D, 2 for 2D
    _mode = 1


    def __init__(self, file_name, size=11):
        """Initialize, open data file (his) and open plot window
        (size parameter decides on plot dimensions)

        """
        self.file_name = file_name
        # The current (active) file
        self.hisfile = None
        self.load(file_name)

        # Peaks for fitting
        self.peaks = []
        
        # plotter front-end
        self.plotter = plotter.Plotter(size)


    def load(self, file_name):
        """Load his file (also tar gzipped files)"""
        self.hisfile = hisfile.HisFile(file_name)


    @property
    def mode(self):
        """ 1D or 2D plotting mode"""
        return Experiment._mode


    @mode.setter
    def mode(self, mode):
        """Deactivate all plots that have different mode (dimension)"""
        if mode not in [1, 2]:
            raise GeneralError('Only 1D and 2D plotting modes are possible')

        if mode == 2:
            self.plotter.ylin()

        Experiment._mode = mode
        for p in self.plots:
            if p.histogram.dim != mode:
                p.active = False


    def _replace_latex_chars(self, text):
        """Clear text from characters that are not accepted by latex"""
        replace_chars = [['_', '-'],
                            ['$', '\$'],
                            ['%', '\%'],
                            ['~', ' '],
                            ['"', "''"],
                            ['\\', ' ']]
        replaced_text = text
        for r_ch in replace_chars:
            replaced_text = replaced_text.replace(r_ch[0], r_ch[1])
        return replaced_text


    def show_registers(self):
        """Print the available registers"""
        i = -1
        print('1D histograms')
        print('{: <3} {: ^40} {: ^5} {: ^8} {: ^8}'.\
                format('i', 'Title', 'Bin', 'Norm', 'Active'))
        print('-' * 79)

        for p in reversed(Experiment.plots):
            print('{: >3} {: <40} {: >5} {: >5.2e} {: >5}'.\
                    format(i, p.histogram.title[:40], p.bin_size,
                           p.norm, p.active))
            i -= 1
        print()

        i = -1
        print('2D histograms')
        print('{: <3} {: ^40} {: ^5} {: ^8} {: ^8}'.\
                format('i', 'Title', 'Bin', 'Norm', 'Active'))
        print('-' * 79)

        for p in reversed(Experiment.maps):
            print('{: >3} {: <40} {: >5} {: >5.2e} {: >5}'.\
                    format(i, p.histogram.title[:40], p.bin_size,
                           p.norm, p.active))
            i -= 1
        print()


    def _expand_norm(self, norm, num_of_args):
        """Return normalization array of lenght equal to 
        num_of_args, expand integers to whole array, check 
        if list is of proper lenght

        """
        normalization = []
        if isinstance(norm, str):
            if norm.lower() == 'area':
                for i in range(num_of_args):
                    normalization.append('area')
            else:
                print("Normalization must be a float, ",
                    "list of floats or a 'area' string")
                return None
        elif isinstance(norm, float) or isinstance(norm, int):
            for i in range(num_of_args):
                normalization.append(norm)
        elif isinstance(norm, list):
            if len(norm) == num_of_args:
                normalization = norm
            else:
                print('List of normalization factors must be of the same' +
                      ' length as the list of histograms')
                return None
        else:
            print("Normalization must be a float, ",
                  "list of floats or a 'area' string")
            print(norm, ' was given')
            return None
        return normalization


    def _expand_bin_sizes(self, bin_size, num_of_args):
        """See _expand_norm"""
        bin_sizes = []
        if isinstance(bin_size, int):
            for i in range(num_of_args):
                bin_sizes.append(bin_size)
        elif isinstance(bin_size, list):
            if len(bin_size) == num_of_args:
                bin_sizes = bin_size
            else:
                print('List of bin sizes must be of the same' +
                      ' length as the list of histograms')
                return None
        else:
            print("Bin size must be an int or a list of ints")
            return None
        return bin_sizes


    def _expand_d_args(self, args):
        """Expand list of args to a list of histograms ids or Plot
        instances"""
        his_list = []
        for his in args:
            if isinstance(his, int):
                his_list.append(his)
            elif isinstance(his, str):
                try:
                    his_range = his.split('-')
                    his_range = [x for x in range(int(his_range[0]),
                                                int(his_range[1]) + 1)]
                    his_list += his_range
                except (ValueError, IndexError):
                    break
            elif isinstance(his, Plot):
                his_list.append(his)
            else:
                break
        else:
            return his_list
        print("Histogram list must be given in a 'x-y' format,",
                "where x and y are integers",
                "(note also quotation marks), e.g. '100-115'")
        return None



    def d(self, *args, norm=1, bin_size=1, clear=True, use_log=None):
        """
        Plot 1D histogram. 
        * args: is a list of histograms that may be given as:
              - positive integer: is interpreted as the histogram id
                                  from a currently open file
              - negative integer: is interpreted as the registry number
                                  (see (show_registers())
              - Plot object:       see Plot class
              - string:  in 'x-y' format where x and y are integers 
                        (note also mandatory quatation marks)
                        is interpreted as a range of histograms ids

        * norm: may be given as a single float or int value or an 'area' string,
                also a list of length matching the *args list may be used
                with any combination of the above accepted values
        * bin_size: must be an integer, a list of ints is 
                    also accepted (see norm)
        * clear: is True by default, which means that previous plot is 
                 cleared if False is given, the previous plots are not cleared.

        Example:
        e.d(100, plot1, '105-106', -3, bin_size=[1, 2, 1, 1, 10], clear=False)

        """
        plots = []

        his_list = self._expand_d_args(args)

        normalization = self._expand_norm(norm, len(his_list))
        if normalization is None:
            return None

        bin_sizes = self._expand_bin_sizes(bin_size, len(his_list))
        if bin_sizes is None:
            return None

        # Clear the plotting area (of clear is False, the currently
        # active plots are not deactivated, so they got replotted at
        # the end of this function)
        self.plotter.clear()

        # Switch mode to 1D
        self.mode = 1
        # Deactivate current plots if clear flag is used
        if clear:
            for p in Experiment.plots:
                p.active = False

        if use_log is not None and type(use_log) == bool:
            self.logy = use_log

        # Prepare data for plotting
        for i_plot, his in enumerate(his_list):
            if isinstance(his, int):
                # load histograms from the file
                if his > 0:
                    data = self.hisfile.load_histogram(his)
                    if data[0] != 1:
                        print('{} is not a 1D histogram'.format(his))
                        return None
                    title = self.hisfile.histograms[his]['title'].strip()
                    title = '{}:{}'.format(his, 
                                           self._replace_latex_chars(title))
                    histo = histogram.Histogram()
                    histo.title = title
                    histo.x_axis = data[1]
                    histo.weights = data[3]
                    histo.errors = self._standard_errors_array(data[3])
                    plot = Plot(histo, 'histogram', True)
                    plot.bin_size = bin_sizes[i_plot]
                    plot.norm = normalization[i_plot]
                    plots.append(plot)
                    Experiment.plots.append(plot)
                else:
                    # plot histograms from registry
                    # Numbered by negative numbers (-1 being the latest)
                    # Call show_registers for a list of available plots
                    try:
                        plot = Experiment.plots[his]
                        Experiment.plots[his].active = True
                        Experiment.plots[his].bin_size = bin_sizes[i_plot]
                        Experiment.plots[his].norm = normalization[i_plot]
                    except IndexError:
                        print('There is no plot in the registry under the',
                              'number', his, 'use show_registry() to see',
                              'available plots')
                        return None
                    plots.append(plot)
            elif isinstance(his, Plot):
                # If instance of Plot class is given, mark it active and add
                # to the deque (if not already there)
                # and to the array to be returned at the end
                his.active = True
                his.bin_size = bin_sizes[i_plot]
                his.norm = normalization[i_plot]
                plots.append(his)
                if his not in Experiment.plots:
                    Experiment.plots.append(his)

        # Count the number of active plots
        active_plots = 0
        for plot in Experiment.plots:
            if plot.active:
                active_plots += 1
        print(str(self.logy))
        # Here the actual plotting happens
        i_plot = 0
        for plot in Experiment.plots:
            if plot.active:
                i_plot += 1
                # If ylim is not given explicitely, go through the
                # active plots to find the plot limits
                # This is run only for the last plot.
                # Note that this is neccesary as matplotlib is not
                # autoscaling Y axis when 
                # changing the X axis is being changed
                # If, in a future, the behaviour of matplotlib
                # changes, this part may dropped
                ylim = None
                if self.ylim is None and i_plot == active_plots:
                    ylim = self._auto_scale_y()
                else:
                    ylim = self.ylim

                # Note that ylim is autoscaled above if self.ylim is None
                # But we still keep self.ylim None, 
                # to indicate autoscaling
                self.plotter.plot1d(plot, Experiment.xlim, ylim, self.logy)

        # Return plots that were added or activated
        return None#plots


    def _auto_scale_y(self):
        """Find the y limits taking into account all active plots """
        ylim = [None, None]
        for p in Experiment.plots:
            if p.active:	
                histo = p.histogram
                #if p.bin_size > 1:
                    #histo = histo.rebin1d(p.bin_size)
                #if p.norm != 1:
                    #histo = histo.normalize1d(p.norm, p.bin_size)
                if Experiment.xlim is None:
                    ymin = min(histo.weights)
                    ymax = max(histo.weights)
                else:
                    i_xmin = Experiment.xlim[0] // p.bin_size - 1
                    if i_xmin < 0:
                        i_xmin = 0
                    i_xmax = Experiment.xlim[1] // p.bin_size + 1
                    try:
                        ymin = min(histo.weights[i_xmin:i_xmax])
                    except ValueError:
                        ymin = None
                    try:
                        ymax = max(histo.weights[i_xmin:i_xmax])
                    except ValueError:
                        ymax = None
                if ymin is not None:
                    if ylim[0] is not None:
                        if ymin < ylim[0]:
                            ylim[0] = ymin
                    else:
                        ylim[0] = ymin
                if ymax is not None:
                    if ylim[1] is not None:
                        if ymax > ylim[1]:
                            ylim[1] = ymax
                    else:
                        ylim[1] = ymax
        if ylim[0] is None or ylim[1] is None:
            return None
        else:
            return [ylim[0] - ylim[0] * 0.1, ylim[1] + ylim[1] * 0.1]


    def _auto_scale_x(self):
        """Find the x axis limits taking into account all active plots."""
        xlim = [None, None]
        for p in Experiment.plots:
            if p.active:
                histo = p.histogram
                if Experiment.xlim is None:
                    xmin = histo.x_axis[0]
                    xmax = histo.x_axis[-1]
                    if xlim[0] is not None:
                        if xmin < xlim[0]:
                            xlim[0] = xmin
                    else:
                        xlim[0] = xmin
                    if xlim[1] is not None:
                        if xmax > xlim[1]:
                            xlim[1] = xmax
                    else:
                        xlim[1] = xmax

        if xlim[0] is None or xlim[1] is None:
            return None
        else:
            return xlim


    def dl(self, x0=None, x1=None):
        """Change x range of 1D histogram"""
        if self.mode != 1:
            return None

        if x0 is None or x1 is None:
            Experiment.xlim = None
            self.plotter.xlim(self._auto_scale_x())
        else:
            Experiment.xlim = (x0, x1)
            self.plotter.xlim(Experiment.xlim)

        if self.ylim is None:
            self.plotter.ylim(self._auto_scale_y())
        legend = []
        for p in Experiment.plots:
            if p.active:
                title = p.histogram.title
                title = title[:title.index('sum')+4]
                if Experiment.xlim is not None:
                    legend.append(title + str(p.histogram.weights[Experiment.xlim[0]:Experiment.xlim[1]].sum()))
                else: 
                    legend.append(title + str(p.histogram.weights.sum()))
        if self.plotter.legend:
            plt.legend(legend,loc=0, numpoints=1, fontsize='small')


    def dmm(self, y0=None, y1=None):
        """Change yrange of 1D histogram """
        if self.mode != 1:
            return None

        if y0 is None or y1 is None:
            self.ylim = None
        else:
            self.ylim = (y0, y1)

        if self.ylim is None:
            self.plotter.ylim(self._auto_scale_y())
        else:
            self.plotter.ylim(self.ylim)


    def log(self):
        """Change y scale to log or z scale to log"""
        if self.mode == 1:
            self.plotter.ylog()
            self.logy = True
        elif self.mode == 2:
            Experiment.logz = True
            self.dd(-1, xc=Experiment.xlim2d, yc=Experiment.ylim2d)


    def lin(self):
        """Change y scale to linear or z scale to linear"""
        if self.mode == 1:
            self.plotter.ylin()
            self.logy = False
        if self.mode == 2:
            Experiment.logz = False
            self.dd(-1, xc=Experiment.xlim2d, yc=Experiment.ylim2d)


    def list(self, his_id=None):
        """List all histograms in the active data file
           or details on a selected histogram. Now accepts '1d','1D','2d',
           or '2D' as input for listing all 1 or 2 dimensional histograms. 
           Now also implements re to query the list (case insensitive)"""
        if his_id is None:
            for key in sorted(self.hisfile.histograms.keys()):
                print('{: <6} {}'.format(key, 
                                    self.hisfile.histograms[key]['title']))
        elif isinstance(his_id, str):
            if his_id is '1d' or his_id is'1D':
               for key in sorted(self.hisfile.histograms.keys()):
                   if self.hisfile.histograms[key]['dimension']==1:
                       print('{: <6} {}'.format(key, 
                                    self.hisfile.histograms[key]['title']))
            elif his_id is '2d' or his_id is'2D':
               for key in sorted(self.hisfile.histograms.keys()):
                   if self.hisfile.histograms[key]['dimension']==2:
                       print('{: <6} {}'.format(key, 
                                    self.hisfile.histograms[key]['title']))
            else:
               for key in sorted(self.hisfile.histograms.keys()):
                   if re.search(his_id,self.hisfile.histograms[key]['title'],re.I)!=None:
                      print('{: <6} {}'.format(key, 
                                    self.hisfile.histograms[key]['title']))
        else:
            try:
                dim = self.hisfile.histograms[his_id]['dimension']
                xmin = []
                xmax = []
                for i in range(dim):
                    xmin.append(self.hisfile.histograms[his_id]['minc'][0])
                    xmax.append(self.hisfile.histograms[his_id]['maxc'][0])
                print('{: <10} : {}'.format('ID', his_id))
                print('{: <10} : {}'.format('Title', 
                                    self.hisfile.histograms[his_id]['title']))
                print('{: <10} : {}'.format('Dimensions', dim))
                print('{: <10} : ({}, {})'.format('X range', xmin[0], xmax[0]))
                if dim > 1:
                    print('{: <10} : ({}, {})'.format('Y range', 
                                                      xmin[1], xmax[1]))
            except KeyError:
                print('Histogram id = {} not found'.format(his_id))

    def _standard_errors_array(self, data):
        """ Calculate standard error array (\sigma_i = \sqrt{n_i}),
           with a twist: if n_i = 0, the uncertainity is 1 (not 0)

        """
        errors = np.zeros(data.shape)
        for index, d in np.ndenumerate(data):
            if d == 0:
                errors[index] = 1
            else:
                errors[index] = math.sqrt(abs(d))
        return errors


    def _add_errors(self, error1, error2):
        """Add two error arrays
        \sigma = \sqrt{\sigma_1^2 + \sigma_2^2}

        """
        if error1.shape != error2.shape:
            raise GeneralError('Shape of array mismatches')
        errors = np.zeros(error1.shape)
        for index, d in np.ndenumerate(error1):
            errors[index] = math.sqrt(error1[index]**2 + error2[index]**2)
        return errors


    def gx(self, his, gate_x, gate_y=None, bg_gate=None, norm=1,
           bin_size=1, clear=True, plot=True):
        """Make projection on Y axis of 2D histogram with gate
        set on X (gate_x) and possibly on Y (gate_y)

        his: is a histogram id in a file
        gate_x: is range of bins in (x0, x1) format, this selects the
                range of X columns to be projected on Y axis
        gate_y: is a range of bins in (y0, y1) format (optional), this
                truncates the range of the projection along the Y axis
        bg_gate: is a range of bins in (x0, x1) format (optional), this
                selects the background gate that is subtracted from the
                selected gate_x
        norm: normalization factor (see d())
        bin_size: binning factor (see d())
        clear: True by default, clears previous plots
        plot: True by default, if False no plotting is taking place, 
              only the plot object is being returned
        
        """
        if gate_x is None or len(gate_x) != 2:
            print('Please select gate on X in a (min, max) format')
            return None
        if gate_y is not None and len(gate_y) != 2:
            print('Please select gate on Y in a (min, max) format')
            return None

        # If clear flag used, clear the plotting area
        if clear and plot:
            self.plotter.clear()

        # Switch mode to 1D
        self.mode = 1
        # Deactivate all plots if clear flag is used
        if clear and plot:
            for p in Experiment.plots:
                p.active = False

        data = self.hisfile.load_histogram(his)
        if data[0] != 2:
            print('{} is not a 2D histogram'.format(his))
            return None

        # x for x_axis data
        # y for y_axis data
        # w for weights
        # g for gate (result)
        # bg for background gate
        x = data[1]
        y = data[2]
        w = data[3]
        if gate_y is None:
            gate_y = [0, len(y)-2]
        y = y[gate_y[0]:gate_y[1]+1]
        g = w[gate_x[0]:gate_x[1]+1, gate_y[0]:gate_y[1]+1].sum(axis=0)
        dg = self._standard_errors_array(g)
        if bg_gate is not None:
            if (bg_gate[1] - bg_gate[0]) != (gate_x[1] - gate_x[0]):
                print('#Warning: background and gate of different widths')
            bg = w[bg_gate[0]:bg_gate[1]+1, gate_y[0]:gate_y[1]+1].sum(axis=0)
            g = g - bg
            # Note that since the gate is adding bins, the formula
            # used for standard error is no longer valid
            # This approximation should be good enough though
            dbg = self._standard_errors_array(bg)
            dg = self._add_errors(dg, dbg)

        title = '{}:{} gx({},{})'.format(his, self.hisfile.\
                                         histograms[his]['title'].strip(),
                                         gate_x[0], gate_x[1])
        if bg_gate is not None:
            title += ' bg ({}, {})'.format(bg_gate[0], bg_gate[1])
        title = self._replace_latex_chars(title)

        histo = histogram.Histogram()
        histo.title = title
        histo.x_axis = y
        histo.weights = g
        histo.errors = dg
        gate_plot = Plot(histo, 'histogram', True)
        gate_plot.bin_size = bin_size
        gate_plot.norm = norm

        if plot:
            Experiment.plots.append(gate_plot)
            ylim = None
            if self.ylim is None:
                ylim = self._auto_scale_y()
            else:
                ylim = self.ylim
            self.plotter.plot1d(gate_plot, Experiment.xlim, ylim, self.logy)

        return gate_plot


    def gy(self, his, gate_y, gate_x=None, bg_gate=None, norm=1,
           bin_size=1, clear=True, plot=True):
        """Make projection on X axis of 2D histogram with gate
        set on Y (gate_y) and possibly on X (gate_x)
        
        see gx for more details
        """
        if gate_y is None or len(gate_y) != 2:
            print('Please select gate on Y in a (min, max) format')
            return None
        if gate_x is not None and len(gate_x) != 2:
            print('Please select gate on X in a (min, max) format')
            return None

        # If clear flag used, clear the plotting area
        if clear and plot:
            self.plotter.clear()

        # Switch mode to 1D
        self.mode = 1
        # Deactivate all plots if clear flag is used
        if clear and plot:
            for p in Experiment.plots:
                p.active = False

        data = self.hisfile.load_histogram(his)
        if data[0] != 2:
            print('{} is not a 2D histogram'.format(his))
            return None

        # x for x_axis data
        # y for y_axis data
        # w for weights  
        # g for gate (result)
        # bg for background gate
        x = data[1]
        y = data[2]
        w = data[3]
        if gate_x is None:
            gate_x = [0, len(x)-2]
        x = x[gate_x[0]:gate_x[1]+1]
        g = w[gate_x[0]:gate_x[1]+1, gate_y[0]:gate_y[1]+1].sum(axis=1)
        dg = self._standard_errors_array(g)
        if bg_gate is not None:
            if (bg_gate[1] - bg_gate[0]) != (gate_y[1] - gate_y[0]):
                print('#Warning: background and gate of different widths')

            bg = w[gate_x[0]:gate_x[1]+1, bg_gate[0]:bg_gate[1]+1].sum(axis=1)
            g = g - bg
            # Note that since the gate is adding bins, the formula
            # used for standard error is no longer valid
            # This approximation should be good enough though
            dbg = self._standard_errors_array(bg)
            dg = self._add_errors(dg, dbg)

        title = '{}:{} gy({},{})'.format(his, self.hisfile.\
                                         histograms[his]['title'].strip(),
                                         gate_y[0], gate_y[1])
        if bg_gate is not None:
            title += ' bg ({}, {})'.format(bg_gate[0], bg_gate[1])
        title = self._replace_latex_chars(title)

        histo = histogram.Histogram()
        histo.title = title
        histo.x_axis = x
        histo.weights = g
        histo.errors = dg
        gate_plot = Plot(histo, 'histogram', True)
        gate_plot.bin_size = bin_size
        gate_plot.norm = norm

        Experiment.plots.append(gate_plot)
        if plot:
            ylim = None
            if self.ylim is None:
                ylim = self._auto_scale_y()
            else:
                ylim = self.ylim
            self.plotter.plot1d(gate_plot, Experiment.xlim, ylim, self.logy)

        return gate_plot


    def mark(self, x_mark):
        """Put vertical line on plot to mark the peak (or guide the eye)"""
        plt.axvline(x_mark, ls='--', c='black')


    def annotate(self, x, text, shiftx=0, shifty=0):
        """ Add arrow at x, with annotation text"""
        if self.mode != 1:
            print('Annotation works only for 1D histograms')
            return None

        length = 0.07 * (plt.ylim()[1] - plt.ylim()[0])
        y = self.plots[-1].histogram.weights[x // self.plots[-1].bin_size]
        plt.annotate(text, xy=(x, y),
                    xytext=(x + shiftx, y + length + shifty),
                    rotation=90.,
                    xycoords='data',
                    fontsize=9,
                    verticalalignment='bottom',
                    horizontalalignment='center',
                    arrowprops=dict(width=1, facecolor='black', headwidth=5,
                                    shrink=0.1))


    def load_gates(self, filename):
        """Load gamma gates from text file, the format is:
        # Comment line
        Name    x0  x1  bg0 bg1
        Example:
        110     111 113 115 117

        """
        gatefile = open(filename, 'r')
        lineN = 0
        gates = {}
        for line in gatefile:
            lineN += 1
            line = line.strip()
            if line.startswith('#'):
                continue
            items = line.split()
            if len(items) < 5:
                print('Warning: line {} bad data'.format(lineN))
                continue
            gates[int(items[0])] = ((int(items[1]), int(items[2])),
                                   (int(items[3]), int(items[4])))
        return gates


    def pk(self, *args, **kwargs):
        """Add peaks for gaussian fitting procedure. The args
        give a list of peak energy (approx.), the kwargs may include
        additional parameters (e.g. min or max, etc) used by peak_fitter"""
        for e in args:
            if isinstance(e, int) or isinstance(e, float):
                p = {'E' : e}
                p.update(kwargs)
                self.peaks.append(p)


    def pzot(self):
        """Clear all peaks """
        self.peaks=[]


    def dd(self, his, xc=None, yc=None, logz=None):
        """Plot 2D histogram,

        his may be a positive integer (loads histogram from the data file)
        negative integer (2D plots registry) or Plot instance (must be a 2D
        plot)

        xc is x range, yc is y range, that may be applied immediately, 
        see also xc() and yc() functions

        """
        self.mode = 2

        for p in Experiment.maps:
            p.active = False

        plot = None
        self.plotter.clear()

        if isinstance(his, int):
            if his > 0:
                data = self.hisfile.load_histogram(his)
                if data[0] != 2:
                    print('{} is not a 2D histogram'.format(his))
                    return None

                title = self.hisfile.histograms[his]['title'].strip()
                title = '{}:{}'.format(his, 
                                       self._replace_latex_chars(title))
                histo = histogram.Histogram(dim=2)
                histo.title = title
                histo.x_axis = data[1]
                histo.y_axis = data[2]
                histo.weights = data[3]
                plot = Plot(histo, 'map', True)
                Experiment.maps.append(plot)
            else:
                # plot histogram from the registry
                # Numbered by negative numbers (-1 being the latest)
                # Call show_registers for a list of available plots
                try:
                    plot = Experiment.maps[his]
                    Experiment.maps[his].active = True
                except IndexError:
                    print('There is no 2D plot in the registry under the',
                            'number', his, 'use show_registry() to see',
                            'available plots')
                    return None
        elif isinstance(his, Plot):
            # If instance of Plot class is given, mark it active and add
            # to the deque (if not already there)
            # and to the array to be returned at the end
            if his.histogram.dim != 2:
                print('This {} is not a 2D histogram'.format(his))
                return None
            his.active = True
            plot = his
            if his not in Experiment.maps:
                Experiment.maps.append(his)

        if xc is not None:
            Experiment.xlim2d = xc
        if yc is not None:
            Experiment.ylim2d = yc

        if logz is None:
            use_log = Experiment.logz
        else:
            use_log = logz
        if plot is not None:
            self.plotter.plot2d(plot, Experiment.xlim2d, 
                                Experiment.ylim2d, use_log)

        return [plot]


    def xc(self, x0=None, x1=None):
        """Change xrange of a 2D histograms"""
        if self.mode == 2:
            if x0 is None or x1 is None:
                Experiment.xlim2d = None
                xlim = None
                for p in Experiment.maps:
                    if p.active:
                        histo = p.histogram
                        xlim = (histo.x_axis[0], histo.x_axis[-1])
                        break
            else:
                Experiment.xlim2d = (x0, x1)
                xlim = (x0, x1)
            self.dd(-1, xc=xlim, yc=Experiment.ylim2d)


    def yc(self, y0=None, y1=None):
        """Change yrange of a 2D histogram"""
        if self.mode == 2:
            if y0 is None or y1 is None:
                Experiment.ylim2d = None
                ylim = None
                for p in Experiment.maps:
                    if p.active:
                        histo = p.histogram
                        ylim = (histo.y_axis[0], histo.y_axis[-1])
                        break
            else:
                Experiment.ylim2d = (y0, y1)
                ylim = (y0, y1)
            self.dd(-1, xc=Experiment.xlim2d, yc=ylim)


    def add_his(self, *args, fac=1):
        """
        Add together 1D histograms. As in Experiment.d,
        * args: is a list of histograms that may be given as:
              - positive integer: is interpreted as the histogram id
                                  from a currently open file
              - negative integer: is interpreted as the registry number
                                  (see (show_registers())
              - Plot object:       see Plot class
              - string:  in 'x-y' format where x and y are integers 
                        (note also mandatory quatation marks)
                        is interpreted as a range of histograms ids
        fac: is a real number or list of numbers the same length as the number of histograms
            specified by *args. fac is used to multiply weights of the histograms together. 
            Use this function carefully, strange numbers in the histogram, 
            i.e. negative values etc., could give unexpected results. 
        """
        his_list = self._expand_d_args(args)
        
        if type(fac) == list:
            if len(fac) != 1 and len(fac) != len(his_list):
                print('Length of list fac is {}, and not equal to number of specified histograms, {}.'.format(len(fac),len(his_list)))
                return None

        histo = histogram.Histogram()
        histo.title = 'Sum of {} histograms'.format(len(his_list))
        
        his = his_list[0]
        if isinstance(his, int):
            if his > 0:
                data = self.hisfile.load_histogram(his)
                if data[0] != 1:
                    print('{} is not a 1D histogram'.format(his))
                    return None 
                histo.x_axis = data[1]
                bin_size = 1
                length = len(data[1])
                if type(fac) == int or type(fac)==float:
                    histo.weights = data[3]*1.0
                elif type(fac) == list:
                    histo.weights = data[3]*fac[0]*1.0
            else:
                try:
                    plot = Experiment.plots[his]
                    histo.x_axis = plot.histogram.x_axis
                    bin_size = plot.bin_size
                    length = len(histo.x_axis)
                    if type(fac) == int or type(fac)==float:
                        histo.weights = plot.histogram.weights
                    elif type(fac) == list:
                        histo.weights = plot.histogram.weights*fac[0]                  
                except IndexError:
                    print('There is no plot in the registry under the',
                          'number', his, 'use show_registry() to see',
                          'available plots')
                    return None  
        elif isinstance(his, Plot):
            histo.x_axis = his.histogram.x_axis
            bin_size = his.bin_size
            length = len(histo.x_axis)
            if type(fac) == int or type(fac)==float:
                histo.weights = his.histogram.weights
            elif type(fac) == list:
                histo.weights = his.histogram.weights*fac[0]
        
        for i_plot, his in enumerate(his_list[1:]):
            if isinstance(his, int):
                # load histograms from the file
                if his > 0:
                    data = self.hisfile.load_histogram(his)
                    if length != len(data[1]):
                        print('Inconsistent his length at {}'.format(i_plot))
                        return None
                    if data[0] != 1:
                        print('{} is not a 1D histogram'.format(his))
                        return None
                    if type(fac) == int or type(fac)==float:
                        histo.weights += data[3]*fac*1.0
                    elif type(fac) == list:
                        histo.weights += data[3]*fac[i_plot]*1.0
                else:
                    # load histograms from registry
                    # Numbered by negative numbers (-1 being the latest)
                    # Call show_registers for a list of available plots
                    try:
                        plot = Experiment.plots[his]
                        if length != len(plot.histogram.x_axis):
                            print('Inconsistent his length at {}'.format(i_plot))
                            return None
                        if bin_size != plot.bin_size:
                            print('Inconsistent bin_size length at {}'.format(i_plot))                            
                            return None

                        if type(fac) == int or type(fac)==float:
                            histo.weights += plot.histogram.weights*fac
                        elif type(fac) == list:
                            histo.weights += plot.histogram.weights*fac[i_plot]                  
                    except IndexError:
                        print('There is no plot in the registry under the',
                              'number', his, 'use show_registry() to see',
                              'available plots')
                        return None                    
            elif isinstance(his, Plot):
                # If instance of Plot class is given, mark it active and add
                # to the deque (if not already there)
                # and to the array to be returned at the end
                if length != len(his.histogram.x_axis):
                    print('Inconsistent his length at {}'.format(i_plot))
                    return None
                if bin_size != his.bin_size:
                    print('Inconsistent bin_size length at {}'.format(i_plot))
                    return None

                if type(fac) == int or type(fac)==float:
                    histo.weights += his.histogram.weights*fac
                elif type(fac) == list:
                    histo.weights += his.histogram.weights*fac[i_plot]

        histo.errors = self._standard_errors_array(histo.weights)
        plot = Plot(histo, 'histogram', True)
        Experiment.plots.append(plot)
        return plot

    def clear(self):
        self.plotter.clear()


    def color_map(self, cmap=None, clist=False):
        if self.mode == 2:
            self.plotter.color_map(cmap)
            self.dd(-1, xc=Experiment.xlim2d, yc=Experiment.ylim2d)
        if clist:
            maps=[m for m in cm.datad if not m.endswith("_r")]
            print(maps)
               
            

    def fit_peaks(self, his=None, rx=None, clear=True):
        """
        Fit gaussian peaks to 1D plot. If his is not given the
        current plot is used. If rx is not given, the current range is used
        Returns list of lists:
            [E, x0, dx, A, dA, s, Area]
        where E is name of the peak, x0, A and s are fitted parameters
        and d'something' is its uncertainity. Area is total calculated area.

        """
        if rx is None:
            rx = Experiment.xlim
        if len(rx) != 2:
            print('Please use x range in format rx=(min, max), where',
                  'min and max are integers.')
            return None

        # Deactivate all the plots
        for p in Experiment.plots:
            if p.active:
                p.active = False

        peaks = []
        for p in self.peaks:
            if rx[0] <= p.get('E') <= rx[1]:
                peaks.append(p)

        PF = PeakFitter(peaks, 'linear', '')


        if his is not None:
            if hasattr(his,'histogram'):
                x_axis = his.histogram.x_axis
                weights = his.histogram.weights
                title = his.histogram.title
            if isinstance(his, int):
                if his > 0:
                    data = self.hisfile.load_histogram(his)
                    if data[0] != 1:
                        print('{} is not a 1D histogram'.format(his))
                        return None
                    x_axis = data[1]
                    weights = data[3]
                    title = self.hisfile.histograms[his]['title'].strip()
                    title = '{}:{}'.format(his, self._replace_latex_chars(title))
                else:
                    try:
                        x_axis = Experiment.plots[his].histogram.x_axis
                        weights = Experiment.plots[his].histogram.weights
                        title = Experiment.plots[his].histogram.title
                    except IndexError:
                        x_axis=0
                        weights=0
                        title='Err'
                        print('There is no plot in the registry under the',
                              'number', his, 'use show_registry() to see',
                              'available plots')
                        return None
        else:
            x_axis = Experiment.plots[-1].histogram.x_axis
            weights = Experiment.plots[-1].histogram.weights
            title = Experiment.plots[-1].histogram.title
            
        dweights = self._standard_errors_array(weights)
        
        if clear:
            self.clear()

        histo_data = histogram.Histogram()
        histo_data.x_axis = x_axis
        histo_data.weights = weights
        histo_data.errors = dweights
        histo_data.title = title
        plot_data = Plot(histo_data, 'histogram', True)
        # The histogram data is plotted here so the fit function
        # may be overlaid on in. However, the plot_data is appended 
        # to the registry after the fit functions so it is on top of the
        # registry.
        self.plotter.plot1d(plot_data, xlim=None)

        fit_result = PF.fit(x_axis[rx[0]:rx[1]], weights[rx[0]:rx[1]],
                            dweights[rx[0]:rx[1]])

        histo_baseline = histogram.Histogram()
        histo_baseline.x_axis = x_axis[rx[0]:rx[1]]
        histo_baseline.weights = fit_result['baseline']
        histo_baseline.title = 'Baseline'
        plot_baseline = Plot(histo_baseline, 'function', True)
        self.plotter.plot1d(plot_baseline, xlim=rx)

        histo_peaks = histogram.Histogram()
        histo_peaks.x_axis = fit_result['x_axis']
        histo_peaks.weights = fit_result['fit']
        histo_peaks.title = 'Fit'
        plot_peaks = Plot(histo_peaks, 'function', True)

        # Append all the plots to the registry, but
        # keep original data at the end, so the next fit_peaks()
        # call will use then again as default
        Experiment.plots.append(plot_baseline)
        Experiment.plots.append(plot_peaks)
        Experiment.plots.append(plot_data)

        # Plot the last one with the auto_scale if needed
        if Experiment.ylim is None:
            ylim = self._auto_scale_y()
        else:
            ylim = Experiment.ylim

        self.plotter.plot1d(plot_peaks, rx, ylim, self.logy)



        print('#{:^8} {:^8} {:^8} {:^8} {:^8} {:^8} {:^8}'
                .format('Peak', 'x0', 'dx', 'A', 'dA', 's', 'Area'))
        peak_data = []
        for i, peak in enumerate(peaks):
            if peak.get('ignore') == 'True':
                continue
            x0 = PF.params['x{}'.format(i)].value
            dx = PF.params['x{}'.format(i)].stderr
            A = PF.params['A{}'.format(i)].value
            dA = PF.params['A{}'.format(i)].stderr
            s = PF.params['s{}'.format(i)].value
            Area = PF.find_area(x_axis, i)
            #.format functions differently for 3.4+. Now uses the object.__format__
            #if something doesn't have its own __format__. Avoided by making string w/ !s
            #had to remove '.(x)f' from all but first placeholder where (x)=decimal places
            #dvm 2018-05-09
            # to achieve the decimal formatting, currently using round(). Needs revisited
            # to evaluate accuracy of doing this to floats.
            print('{!s:>8} {!s:>8} {!s:>8} {!s:>8} {!s:>8} {!s:>8} {!s:>8}'
                    .format(peaks[i].get('E'), round(x0,2), round(dx,2), round(A,2)
                            , round(dA,2), round(s,2), round(Area,2)))
            peak_data.append([peaks[i].get('E'), x0, dx, A, dA, s, Area])
        return peak_data


    def fit_decay(self, his, gate, cycle, 
                        t_bin=1, time_range=None,
                        model='grow_decay',
                        pars=None,
                        clear=True):
        """Fits decay time profile (grow-in/decay cycle):
        * his: is E-time histogram id
        * gate:  should be given in format:
            ((x0, x1), (bg0, bg1))
        * cycle: is list of beam start, beam stop, cycle end, e.g.
        (0, 100, 300)
        * t_bin: is a binning parameter (optional)
        * time_range: is a gate in time in (t0, t1) format (optional)
        * model: is a model used for fit (see decay_fitter)
                 (default is 'grow_decay')
        * pars is a list of dictionaries (one dict per each parameter)
        (optional, use if model is different than the default one, see
        decay_fitter for details)
            
        """
        if pars is None:
            T0 = {'name' : 'T0', 'value' : cycle[0], 'vary' : False}
            T1 = {'name' : 'T1', 'value' : cycle[1], 'vary' : False}
            T2 = {'name' : 'T2', 'value' : cycle[2], 'vary' : False}
            P1 = {'name' : 'P1', 'value' : 100.0}
            t1 = {'name' : 't1', 'value' : 100.0}
            parameters = [T0, T1, T2, P1, t1]
            if model == 'grow_decay2':
                P2 = {'name' : 'P2', 'value' : 1000.0}
                t2 = {'name' : 't2', 'value' : 1000.0}
                parameters.append(P2)
                parameters.append(t2)
        else:
            parameters = pars

        df = DecayFitter()

        xgate = self.gx(his, gate_x=gate[0], gate_y=time_range, bin_size=t_bin,
                            plot=False)
        bckg = self.gx(his, gate_x=gate[1], gate_y=time_range, bin_size=t_bin,
                          plot=False)

        dyg = self._standard_errors_array(xgate.histogram.weights)
        dyb = self._standard_errors_array(bckg.histogram.weights)

        gate_histo = histogram.Histogram()
        gate_histo.x_axis = xgate.histogram.x_axis
        gate_histo.weights = xgate.histogram.weights - bckg.histogram.weights
        gate_histo.errors = np.sqrt(dyg**2 + dyb**2)
        gate_histo.title = '{}: gx {} bg {} bin {} sum {}'.\
                format(his, gate[0], gate[1], t_bin, gate_histo.weights[gate[0][0],gate[0][1]].sum())
        plot_data = Plot(gate_histo, 'errorbar', True)

        t, n, parameters = df.fit(gate_histo.x_axis, gate_histo.weights,
                                  gate_histo.errors, model, parameters)

        fit_histo = histogram.Histogram()
        fit_histo.x_axis = t
        fit_histo.weights = n
        fit_histo.title = self._replace_latex_chars('Fit: {}'.format(model))
        plot_fit = Plot(fit_histo, 'function', True)

        if clear:
            self.clear()

        self.plotter.plot1d(plot_fit, [cycle[0], cycle[2]], None)
        self.plotter.plot1d(plot_data, [cycle[0], cycle[2]], None)

        Experiment.plots.append(plot_fit)
        Experiment.plots.append(plot_data)

        return parameters


    def gamma_gamma_spectra(self, gg_id, gate, bin_size=1):
        """ 
        Plots gamma-gamma gate broken into 4 subplots (0-600, 600-1200,
        1200-2000, 2000-4000. 
        gg_id is a 2D histogram id
        gate is in form ((x1, y1), (x2, y2)) where i=1 is gate on line, i=2
        is gate on background

        This special plot is not loaded into the registry in a 4 panel
        form, but as a 'standard' plot object
        """
        self.clear()
        plot = self.gy(gg_id, gate[0], bg_gate=gate[1], 
                       bin_size=bin_size, plot=False )
        ranges = (0, 600, 1200, 2000, 4000)
        self.plotter.plot1d_4panel(plot, ranges)

    def st(self,numx,numy,args):
        """
        This command is similar but different to the "st" or stack
        command in damm. Create an array of subplots numx by numy.
        Then disply a multiplot array of list *args). This should work for 
        1 and 2d histograms but ought to be cleaned up.
        """

        self.clear()
        for i in range(numx):
            for j in range(numy):
                if len(args)!=numx*numy: 
                   print('range mismatch')
                   break
                n = i+numx*(j-1) if numy!=1 else j+numy*(i-1) 
                ax = plt.subplot(numx,numy,n)
                ax.set_xlim([args[n].histogram.weights.nonzero()[0][0]-2,args[n].histogram.weights.nonzero()[0][-1]+10])
                ax.set_ylim([0,args[n].histogram.weights.max()*1.66])
                if args[n].histogram.dim==1:                 
                   ax.plot(args[n].histogram.weights,ls='steps-mid',label=args[n].histogram.title)
                   ax.legend()
                else:
                   self.plotter.plot2d(args[n])
        plt.tight_layout()


    def rebin(self,hisd):
        """
        Rebin the last 1 or 2d histogram as specified by hisd. Can be used after a "zoom" or "pan" in the canvas. TBD automated rebinning for faster displaying.
        """
        tup = (plt.xlim(),plt.ylim())
        if hisd==1:
           temp=self.plots[-1]
           tup=self.fence(temp,tup,hisd)
           self.dl(tup[0][0],tup[0][1])
        else:
           temp=self.maps[-1]
           tup=self.fence(temp,tup,hisd)
           self.dd(-1,xc=tup[0],yc=tup[1])


    def fence(self,args,tup,hisd):
        """
        Confine plot regions to the bounds of the data in the histogram.
        """
        x0 = tup[0][0]
        x1 = tup[0][1]
        y0 = tup[1][0]
        y1 = tup[1][1]
        if x0 <= args.histogram.x_axis[0]:
           x0 = args.histogram.x_axis[0]
        if x1 >= args.histogram.x_axis[-1]:
           x1 = args.histogram.x_axis[-1]
        if y0 <= 0:
           y0 = 0
        if hisd==1:
           if y1 >= args.histogram.weights.max():
              y1 = args.histogram.weights.max()*1.33
        else:
           if y1 >= args.histogram.y_axis[-1]:
              y1 = args.histogram.y_axis[-1]
        return ((x0,x1),(y0,y1))     

    def trace_explorer(self,his,start=0,finish=None):
        """
        Adds the ability to examine a 2D trace histogram or range of 1D histograms 
        and use sliders to visualize the effect of a given trapezoidal filter on the traces.
        This is most helpful when setting up a new detector or signal type. 
        """

        import matplotlib.patches as mpt
        from matplotlib.widgets import Slider, Button, RadioButtons

        fig = plt.figure()

        def trap_filter(times,res,L,G):
            """
            Returns the trapezoidal filtered version of the input vector, res according to 
            L (length) and G (gap) of the resultant trapezoid.
            """
            retvec = np.zeros(len(times))
            zidx = times.searchsorted(0)
            for i in range( zidx,len(times) ):
              retvec[i]=(res[i-L+1:i]-res[i-2*L-G+1:i-L-G]).sum()
            return(retvec)

        def tau_adjust(pulse,tau):
            """
            Returns the Tau/Pole-Zero corrected version of the input vector, pulse according to tau.
            """
            from copy import deepcopy as cp

            bls = cp(pulse)
            retvec = cp(pulse)
            bls -= pulse[:100].mean()
            for t in range(3,len(pulse)):
                pz = bls[:t-1].sum()
                retvec[t] += bls[t] + pz/tau 
            return(retvec)

        def zero_crossing(trap):
            """
            Returns the CFD version of the input vector, trap.
            """
            from copy import deepcopy as cp

            delay = cp(trap)
            td = 20 #time delay 
            cf = .8 #constant fraction
            delay[:-td] += -cf*trap[td:] 
            return(delay)

        def update_te(val):
            slen.val = int(slen.val)
            length = slen.val
            slen.valtext.set_text(length)
            sgap.val = int(sgap.val)
            gap = sgap.val
            sgap.valtext.set_text(gap)
            sid.val = int(sid.val)
            trace_id = sid.val
            sid.valtext.set_text(trace_id)
            tau = 10**stau.val
            stau.valtext.set_text(tau)
            
            pulse[pulse_len:] =weights[:,trace_id][:pulse_len]
            pulse[:pulse_len] =weights[:,trace_id][2]
            pz = tau_adjust(pulse, tau)
            ff = trap_filter(t,pz,length,gap)
            zc = zero_crossing(ff)
            l.set_ydata( pulse )
            l2.set_ydata( pz )
            l3.set_ydata( ff )
            l4.set_ydata( zc )
            ax1.set_ylim(pulse.min()-margin,pulse.max()+margin)
            ax2.set_ylim(pz.min()-margin,pz.max()+margin)
            ax3.set_ylim(ff.min()-margin,ff.max()+margin)
            ax4.set_ylim(zc.min()-margin,zc.max()+margin)
            fig.canvas.draw_idle()
    
        #starting positions for sliders
        l0=100
        g0=200
        tau=1
        
        histo = self.hisfile.load_histogram(his)
        weights = histo[3]
        dim = histo[0]

        if finish==None and dim == 2:
            finish = weights[10].nonzero()[0][-1]
        elif finish==None:
            finish = start + 1 

        if dim == 2:
            pulse_histo = weights[:,start]
        else:
            pulse_histo = weights 
        pulse_len = pulse_histo.nonzero()[0][-1]+1

        pulse = np.zeros(2*pulse_len)
        pulse[pulse_len:] += pulse_histo[:pulse_len]
        pulse[:pulse_len] += pulse_histo[2]
        t = np.arange(-pulse_len,pulse_len,1)  

        ax1 = plt.subplot(3,2,1)
        ax2 = plt.subplot(3,2,2,sharex=ax1)
        ax3 = plt.subplot(3,2,3,sharex=ax1)
        ax4 = plt.subplot(3,2,4,sharex=ax1)
        margin = 100
    
        pz = tau_adjust(pulse,tau)
        ff = trap_filter(t,pz,l0,g0)
        zc = zero_crossing(ff)
    
        l,= ax1.plot(t,pulse,lw=2,color='red')
        ax1.legend(['Input Pulse'])
        l2,= ax2.plot(t,pz,lw=2,color='k')
        ax2.legend(['Pole-zero/Tau Corrected'])
        l3,= ax3.plot(t,ff,lw=2,color='blue')
        ax3.legend(['Trapezoidal Filter Output'])
        l4,= ax4.plot(t,zc,lw=2,color='green')
        ax4.legend(['CFD Output'])
    
        ax2.set_xlim(0,pulse_len)
        ax1.set_ylim(pulse.min()-margin,pulse.max()+margin)
        ax2.set_ylim(pz.min()-margin*10,pz.max()+margin*10)
        ax3.set_ylim(ff.min()-margin*10,ff.max()+margin*10)
        ax4.set_ylim(zc.min()-margin*10,zc.max()+margin*10)
    
        axlen = plt.axes([0.15,0.17, 0.65, 0.03])
        axgap = plt.axes([0.15,0.21, 0.65, 0.03])
        axid = plt.axes([0.15,0.13, 0.65, 0.03])
        axtau = plt.axes([0.15,0.09, 0.65, 0.03])
        slen = Slider(axlen, 'Length', 1, 1000.0, valinit=l0)
        sgap = Slider(axgap, 'Gap', 1, 1000.0, valinit=g0)
        sid = Slider(axid, 'Trace id', start, finish, valinit=start)
        stau = Slider(axtau, 'Tau', -1, 4, valinit=tau)


        slen.on_changed(update_te)
        sgap.on_changed(update_te)
        sid.on_changed(update_te)
        stau.on_changed(update_te)

if __name__ == "__main__":
    pass
