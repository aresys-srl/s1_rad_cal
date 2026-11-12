---
icon: lucide/cloudy
tags:
    - attenuation
    - atmosphere
    - ITU-R
    - weather
---

# Atmospheric Attenuation

The [ITU-R Recommendation P.676](https://www.itu.int/rec/R-REC-p.676/en), published by the International Telecommunication Union (ITU), Radiocommunication Sector (ITU-R),
describes methods for calculating the attenuation of radio waves caused by atmospheric gases, primarily oxygen (O₂) and water vapour (H₂O).
When an electromagnetic wave propagates through the Earth's atmosphere, part of its energy is absorbed by atmospheric molecules, oxygen and water vapour being the two main contributors.
This absorption causes a reduction in the received signal power, commonly expressed as atmospheric attenuation in decibels (dB).
Recommendation P.676 provides mathematical models and computational procedures to estimate this attenuation as a function of:

- frequency
- pressure
- temperature
- water vapour density
- elevation angle

Atmospheric attenuation occurs because oxygen and water-vapour molecules have resonant rotational transitions. When the frequency of an electromagnetic wave
approaches one of these molecular absorption frequencies, energy is transferred from the electromagnetic wave to the atmospheric molecules.

The total specific attenuation is expressed as:

$$
\gamma = \gamma_o + \gamma_w
$$

being $\gamma$ total gaseous specific attenuation (dB/km), and $\gamma_o$ and $\gamma_w$ the oxygen and water contributions, respectively.

The total attenuation $A$ (db) along a propagation path is obtained by integrating the specific attenuation over the path:

$$
A = \int_0^L \gamma(s) ds
$$

For Sentinel-1 acquisitions, the path length is equal to two times the slant range distance.

!!! Tip
    Sentinel-1 operates in the C-band, at a centre frequency of approximately 5.405 GHz.
    At this frequency, atmospheric gaseous absorption by oxygen and water vapour is generally very small, and often negligible.

## Implementation

In order to compute the atmospheric attenuation, `s1-rad-cal` makes use of the [ITU-Rpy package](https://itu-rpy.readthedocs.io/en/latest/index.html), that provides a python implementation
of the [ITU-R Recommendation P.676](https://www.itu.int/rec/R-REC-p.676/en). In particular, the user can choose whether to use the `approx` or `exact` method 
in the `s1-rad-cal` configuration. If `approx` the method described in Annex 2 of the [ITU-R Recommendation P.676](https://www.itu.int/rec/R-REC-p.676/en) is used, otherwise the method
described in Annex 1 is used.

## Weather Dataset

As mentioned above this model requires as input values for temperature, pressure, and water vapour density. `s1-rad-cal` provides two [CLI utilities](CLI.md#cli-utilities) to download weather datasets
from the [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/) in the format required by this tool. In order to use these functionalities, the user must first [setup the
CDS API key](https://cds.climate.copernicus.eu/how-to-api).