---
icon: lucide/audio-lines
tags:
    - de-noising
    - thermal noise
    - noise vectors
---

# Thermal De-Noising

Noise vectors are reported in Sentinel-1 products metadata. In order to apply noise removal to SLC products this tool subtracts the interpolated noise power from the original pixel intensity, leaving the phase unchanged. Since negative power would be unphysical, any pixel whose de-noised intensity falls below zero is clipped to zero.

Being $z$ the calibrated SLC complex pixel value, $\eta$ the noise power, the denoised pixel value $z_{den}$ is given by:

$$
z_{den} = \begin{cases} 
      z \sqrt{\frac{\max(|z^2| - \eta, 0)}{|z^2|}} & \text{ if  } z \neq 0  \\
      0 & \text{otherwise}
\end{cases}
$$

Users can provide external noise vector files: to do so a folder containing **ALL** expected calibration noise xml files must be provided. 
The folder must contain one xml file for each channel, with the same name of the original calibration noise xml file.
See [configuration](CLI.md#configuration-file) for more information.