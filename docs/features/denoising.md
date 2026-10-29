---
icon: lucide/audio-lines
tags:
    - de-noising
    - thermal noise
    - noise vectors
---

# Thermal De-Noising

Noise vectors are reported in Sentinel-1 products metadata. In order to apply noise removal to SLC products this tool subtracts the interpolated noise power from the original pixel intensity,
leaving the phase unchanged.
Since negative power would be non-physical, the default configuration enables clipping, meaning that any pixel whose de-noised intensity falls below zero is instead set to zero.

Being $z$ the calibrated SLC pixel complex value, $\eta$ the noise power, the de-noised pixel value $z_{den}$ with clipping active is given by:

$$
z_{den} = \begin{cases} 
      z \sqrt{\frac{\max(|z^2| - \eta, 0)}{|z^2|}} & \text{ if  } z \neq 0  \\
      0 & \text{otherwise}
\end{cases}
$$

If instead clipping is disabled, the de-noised pixel value $z_{den}$ is given by:

$$
z_{den} = \begin{cases} 
      \operatorname{sign}(|z^2| - \eta) \cdot z \sqrt{\frac{|z^2| - \eta}{|z^2|}} & \text{ if  } z \neq 0  \\
      0 & \text{otherwise}
\end{cases}
$$



The de-noising is performed in a similar way for GRD products: being $x$ the calibrated GRD pixel real value, $\eta$ the noise power, the de-noised pixel value $x_{den}$ with clipping enabled is given by:

$$
x_{den} = \sqrt{\max(|x^2| - \eta, 0)}
$$

If instead clipping is disabled, the de-noised pixel value $x_{den}$ is given by:

$$
x_{den} = \operatorname{sign}(|x^2| - \eta) \cdot \sqrt{|x^2| - \eta}
$$

!!! danger

    Disabling clipping to zero may improve the statistical properties of multilooking or pooling operations. However, it can introduce non-physical values
    and compromise the validity or compatibility of subsequent processing steps.

Users can provide external noise vector files: to do so a folder containing **ALL** expected calibration noise xml files must be provided. 
The folder must contain one xml file for each channel, with the same name of the original calibration noise xml file.
See [configuration](CLI.md#configuration-file) for more information.