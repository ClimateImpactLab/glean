# -*- coding: utf-8 -*-
################################################################################
# Copyright 2014, Distributed Meta-Analysis System
################################################################################

"""
This file provides methods for extracting data from impact bundles (.nc4 files)
"""

__copyright__ = "Copyright 2014, Distributed Meta-Analysis System"

__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jarising@gmail.com"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import numpy as np
from netCDF4 import Dataset
from derive.api import configs

deltamethod_vcv = None


def read_region(config, *args, **kwargs):
    """Snip-out target regions from nc4 file

    Quick and dirty hax to reduce the size of data read in from netCDF files.
    Keeps a memory leak in the module from blowing up the script. Not
    the best way to handle this.

    Parameters
    ----------
    config : dict
        Run configuration dictionary. Used to parse out target regions.
    *args :
        Passed on to read().
    **kwargs :
        Passed on to read().

    Returns
    -------
    years : array-like
    regions : array-like
    data : array-like
    """
    years, regions, data = read(*args, **kwargs)

    if configs.is_allregions(config):
        regions_msk = np.ones(regions.shape, dtype="bool")
    else:
        target_regions = configs.get_regions(config, regions)
        regions_msk = np.isin(regions, target_regions)

    return years, regions[regions_msk], data[..., regions_msk]


def read(filepath, column="rebased", deltamethod=False):
    """If deltamethod is True, treat as a deltamethod file."""
    global deltamethod_vcv

    try:
        rootgrp = Dataset(filepath, "r", format="NETCDF4")
    except Exception as ex:
        import traceback  # CATBELL

        print(
            "".join(traceback.format_exception(ex.__class__, ex, ex.__traceback__))
        )  # CATBELL
        print("Error: Cannot read %s" % filepath)
        exit()

    years = rootgrp.variables["year"][:]
    regions = rootgrp.variables["regions"][:]

    if deltamethod is None:
        # Infer from the file
        deltamethod = "vcv" in rootgrp.variables

    if deltamethod:
        data = rootgrp.variables[column + "_bcde"][:, :, :]
        if deltamethod_vcv is None:
            deltamethod_vcv = rootgrp.variables["vcv"][:, :]
        else:
            assert np.all(deltamethod_vcv == rootgrp.variables["vcv"][:, :])
    else:
        data = rootgrp.variables[column][:, :]

    rootgrp.close()

    # Correct bad regions in costs
    if (
        filepath[-10:] == "-costs.nc4"
        and not isinstance(regions[0], str)
        and not isinstance(regions[0], str)
        and np.isnan(regions[0])
    ):
        rootgrp = Dataset(filepath.replace("-costs.nc4", ".nc4"), "r", format="NETCDF4")
        regions = rootgrp.variables["regions"][:]
        rootgrp.close()

    return years, regions, data


def iterate_regions(filepath, column, config={}):
    global deltamethod_vcv

    do_deltamethod = (
        False
        if configs.is_parallel_deltamethod(config)
        else config.get("deltamethod", None)
    )
    if column is not None or "costs" not in filepath:
        years, regions, data = read_region(
            config,
            filepath,
            column if column is not None else "rebased",
            do_deltamethod,
        )
    else:
        years, regions, data1 = read_region(
            config, filepath, "costs_lb", do_deltamethod
        )
        years, regions, data2 = read_region(
            config, filepath, "costs_ub", do_deltamethod
        )
        data = data2 / 1e5

    if deltamethod_vcv is not None and not config.get("deltamethod", False):
        # Inferred that these were deltamethod files
        config["deltamethod"] = True

    if config.get("multiimpact_vcv", None) is not None and deltamethod_vcv is not None:
        assert isinstance(config["multiimpact_vcv"], np.ndarray)
        # Extend data to conform to multiimpact_vcv
        foundindex = None
        for ii in range(
            config["multiimpact_vcv"].shape[0] - deltamethod_vcv.shape[0] + 1
        ):
            if np.allclose(
                deltamethod_vcv,
                config["multiimpact_vcv"][
                    ii : (ii + deltamethod_vcv.shape[0]),
                    ii : (ii + deltamethod_vcv.shape[1]),
                ],
            ):
                foundindex = ii
                break
        if foundindex is None:
            print(
                np.sum(
                    np.abs(
                        deltamethod_vcv
                        - config["multiimpact_vcv"][
                            : deltamethod_vcv.shape[0], : deltamethod_vcv.shape[1]
                        ]
                    )
                )
            )
            print(
                np.sum(
                    np.abs(
                        deltamethod_vcv
                        - config["multiimpact_vcv"][
                            deltamethod_vcv.shape[0] :, deltamethod_vcv.shape[1] :
                        ]
                    )
                )
            )
        assert foundindex is not None, (
            "Cannot find the VCV for " + filepath + " within the master VCV."
        )
        newdata = np.zeros(
            tuple([config["multiimpact_vcv"].shape[0]] + list(data.shape[1:]))
        )
        if len(data.shape) == 2:
            newdata[foundindex : (foundindex + deltamethod_vcv.shape[0]), :] = data
        else:
            newdata[foundindex : (foundindex + deltamethod_vcv.shape[0]), :, :] = data
        data = newdata

        deltamethod_vcv = None  # reset for next file

    config["regionorder"] = list(regions)

    if configs.is_allregions(config):
        yield "all", years, data
        return

    regions = list(regions)
    for region in configs.get_regions(config, regions):
        ii = regions.index(region)
        if config.get("deltamethod", False) and not configs.is_parallel_deltamethod(
            config
        ):
            yield regions[ii], years, data[:, :, ii]
        else:
            yield regions[ii], years, data[:, ii]


def iterate_values(years, values, config={}):
    """
    Config options: yearsets, years
    """

    if "yearsets" in config and config["yearsets"]:
        yearsets = config["yearsets"]
        if yearsets:
            yearsets = [(2000, 2019), (2020, 2039), (2040, 2059), (2080, 2099)]

        for yearset in yearsets:
            if isinstance(yearset, list):
                yearset = tuple(yearset)
            if config.get("deltamethod", False):
                if values.ndim == 1:
                    yield "%d-%d" % yearset, np.mean(
                        values[
                            :, np.logical_and(years >= yearset[0], years < yearset[1])
                        ],
                        axis=1,
                    )
                else:  # multiple regions included
                    yield "%d-%d" % yearset, np.mean(
                        values[
                            :,
                            np.logical_and(years >= yearset[0], years < yearset[1]),
                            :,
                        ],
                        axis=1,
                    )
            else:
                if values.ndim == 1:
                    yield "%d-%d" % yearset, np.mean(
                        values[np.logical_and(years >= yearset[0], years < yearset[1])]
                    )
                else:  # multiple regions included
                    yield "%d-%d" % yearset, np.mean(
                        values[
                            np.logical_and(years >= yearset[0], years < yearset[1]), :
                        ],
                        axis=0,
                    )
        return

    years = list(years)
    for year in configs.get_years(config, years):
        if config.get("deltamethod", False) and not configs.is_parallel_deltamethod(
            config
        ):
            if values.ndim == 2:
                yield year, values[:, years.index(year)]
            else:
                yield year, values[:, years.index(year), :]
        else:
            if values.ndim == 1:
                yield year, values[years.index(year)]
            else:
                yield year, values[years.index(year), :]
