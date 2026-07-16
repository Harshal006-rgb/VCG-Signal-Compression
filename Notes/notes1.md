## 5. Target Applications
Due to the computational speed (0.076s processing time) and high signal fidelity, this technology is designed for:

* **Wearable Health Monitoring**: Long-term Holter or ambulatory devices.
* **Telemedicine**: Low-latency transmission of complex cardiac diagnostics over limited mobile networks.
* **Data Archiving**: Compact storage of massive clinical databases without losing crucial diagnostic details.


## 6. Detailed Algorithmic Pipeline

### 📥 Compression Process
1. **Original VCG Signal**: The raw 3D input vector.
2. **Preprocessing**:
   - Low-pass **Butterworth filter** to remove noise.
   - **Normalization** to standardize amplitude.
3. **KL Transform (Karhunen-Loève)**: First-stage decorrelation of spatial components.
4. **Second Rotation**: Performs an additional spatial rotation to align the VCG loop’s primary plane (where QRS & T wave energy is concentrated), resulting in a **Realigned VCG**.
5. **Application of TQWT**: Decomposes the realigned VCG into sparse sub-band components.
6. **DZQ (Dead-Zone Quantization)**: Thresholds small coefficients to zero, creating high sparsity.
7. **Integer Conversion**: Casts the remaining coefficients to integer values.
8. **RLE (Run-Length Encoding)**: Compresses the long sequences of zeroes to produce the final **Compressed VCG Signal**.

### 📤 Reconstruction Process
1. **Compressed VCG Signal**
2. **RLE Decoding**: Restores the quantized integer coefficients.
3. **Inverse TQWT**: Reconstructs the realigned VCG signal.
4. **Inverse Second Rotation**: Reverses the alignment rotation.
5. **Inverse KL Transform**: Converts the signals back to original X, Y, and Z spatial dimensions.
6. **Reconstructed VCG**: Reconstructs the diagnostic-quality signal.

---

## 7. Historical Context & Literature Limitations

According to the study's review of prior research, previous VCG/ECG compression schemes had key limitations:

* **Discrete KL Expansion**: Achieved a CR of 12:1 but suffered from high computational complexity, lacked a fast inverse algorithm, and was limited to a low sampling rate (250 Hz). No PRD was computed.
* **2D DCT & 2D WHT**: Produced low compression ratios (2:1 to 5:1), did not calculate reconstruction distortion (PRD), and used a low sampling rate (250 Hz).
* **Huffman + DCT**: Achieved CRs of 3.02 and 4.15, but at the cost of clinically unacceptable distortion (PRD of 16.9% to 17.2%). Additionally, the dataset used was proprietary.
* **Adaptive Linear Prediction**: Maintained an acceptable PRD range but achieved low compression ratios (3.857 and 4.45).

---

## 8. VCG Electrode Placement & Acquisition Specs
* **Lead System**: Uses orthogonal $Vx$, $Vy$, and $Vz$ lead placements on the patient's chest to capture the 3D heart vector.
* **Hardware Specifications**: 
  - 16-bit resolution
  - Input voltage range of $\pm 16\text{ mV}$
  - Offset compensation up to $\pm 300\text{ mV}$
  - Sensitivity of $0.5\text{ }\mu\text{V/LSB}$ (equivalent to 2000 A/D units per mV)
  - Bandwidth of $0 - 1\text{ kHz}$ with synchronous sampling across all channels
  - Input short-circuited noise level of $\le 10\text{ }\mu\text{V}$ (peak-to-peak) or $3\text{ }\mu\text{V}$ (RMS)


## 9. Mathematical & Signal Processing Details

### 📊 PTB Database Details
* **Demographics**: 549 records from 290 subjects (aged 17–87, mean 57.2 years; 209 men, 81 women). Each subject contributed 1–5 records.
* **Signal Channels**: 15 simultaneous channels: standard 12-lead ECG and 3 Frank leads ($Vx, Vy, Vz$).
* **Sampling Rate**: Digitized at 1000 samples per second ($1000\text{ Hz}$).
* **Resolution**: 16-bit resolution over a range of $\pm 16.384\text{ mV}$.

### 🧹 Preprocessing Steps
1. **Low-Pass Filtering**:
   - Filter Type: **1st-order Low-pass Butterworth filter**.
   - Cutoff Frequency: **$10\text{ Hz}$** (Normalized Cutoff = $\text{cutoff} / f_{\text{nyquist}}$, where $f_{\text{nyquist}} = f_s / 2 = 500\text{ Hz}$).
   - Rationale: Maximally flat frequency response in passband to avoid ripples while attenuating high-frequency noise and artifacts.
2. **Mean Subtraction (DC Offset Removal)**:
   - Subtracts the mean value from each data point.
   - Rationale: Removes DC offset and centers the VCG loop around zero to accurately capture variations.

### 📐 Discrete Karhunen-Loève (K-L) Expansion
* **Matrix Representation**: Preprocessed VCG represents a $3 \times n$ matrix $X$, where $n$ is the number of samples.
* **Function**: Projects the 3D VCG onto an orthogonal basis aligned with directions of maximum variance (principal planes).
* **Role**: Decorrelates the spatial components, concentrating most of the signal energy into a few principal components.

### 🔄 The Second Rotation Mechanics (Loop Alignment)
* **The Stability Problem**: If the two largest eigenvalues are nearly identical, the eigenvectors become unstable and highly sensitive to small perturbations.
* **The Solution**: A secondary rotation using vector alignments.
  - **T Loop Alignment ($p$-axis)**: The T loop has a much smaller angular spread than the QRS loop. The $p$-axis is aligned with the longest vector inside the T loop within the principal plane.
  - **Pan-Tompkins Algorithm**: Used to detect the QRS complexes in the cardiac cycle. Identifying the QRS complex allows the system to accurately locate the T loop.
  - **QRS Rotation ($q$-axis)**: Defined within the principal plane, perpendicular to the $p$-axis. It is oriented such that the QRS loop rotates counter-clockwise in the principal plane.
  - **Out-of-Plane ($r$-axis)**: Established perpendicular to the principal plane.
  - **Coordinate System**: The final $(p, q, r)$ axes form a standardized, right-handed coordinate system. This eliminates inter-patient variability (such as physical heart orientation and chest movement).


## 10. TQWT Mathematics & Scaling Factors

The VCG signal is flattened into a 1-D vector and decomposed into sub-bands using TQWT, which is controlled by three parameters:
* **Q-factor ($q$)**: Determines the quality factor of the wavelets (number of oscillations).
* **Redundancy ($r$)**: Controls the level of redundancy in the transform.
* **Number of Stages ($J$)**: Defines the number of decomposition levels.

### 📐 Scaling Factors Formulas
The scaling factors $\beta$ and $\alpha$ define the low-pass and high-pass sub-band scaling and bandwidth:
$$\beta = \frac{2}{q + 1}$$
$$\alpha = 1 - \frac{\beta}{r}$$

---

## 11. Two-Channel Filter Bank Decomposition

The VCG signal $x(n)$ of length $N$ is first transformed using the unitary Discrete Fourier Transform (DFT) to conserve energy:
$$X(k) = \frac{1}{\sqrt{N}} \sum_{n=0}^{N-1} x(n) e^{-j\frac{2\pi}{N}nk}, \quad 0 \le k \le N-1$$

At each decomposition stage $j$, the low-pass sub-band length $N_0^{(j)}$ and high-pass sub-band length $N_1^{(j)}$ are calculated as:
$$N_0^{(j)} = 2 \left\lfloor \frac{\alpha^j N}{2} \right\rfloor$$
$$N_1^{(j)} = 2 \left\lfloor \frac{\beta \alpha^{j-1} N}{2} \right\rfloor$$

### 🔄 Signal Reconstruction
The signal is reconstructed by combining sub-bands using the synthesis filter bank and applying the inverse DFT:
$$y(n) = \frac{1}{\sqrt{N}} \sum_{k=0}^{N-1} Y(k) e^{j\frac{2\pi}{N}nk}$$

---

## 12. Dead-Zone Quantization (DZQ) Details

DZQ is applied to reduce the number of coefficients by setting small-valued coefficients lying within a threshold interval to zero.

### 📐 Threshold ($Th$)
Based on the maximum ($M$) and minimum ($N$) values of the transform coefficients:
$$Th = \frac{M - N}{32}$$

### 📐 Quantization Step Size ($\Delta$)
Using a scaling factor $\gamma$:
$$\Delta = \gamma \cdot Th$$

### 📐 Decision Intervals ($D_k$) and Reconstructed Outputs ($R_k$)
$$D_k = \begin{cases} (-Th, Th), & \text{if } k = 0 \\ [(2k-1)\Delta, (2k+1)\Delta], & \text{otherwise} \end{cases}$$
$$R_k = \begin{cases} 0, & \text{if } k = 0 \\ k\Delta, & \text{if } k = \pm 1, \pm 2, \dots \end{cases}$$

---

## 13. Reconstructed Evaluation Metrics (Updated)

1. **Fidelity (FID)**: Calculates the similarity between the original ($V_i$) and reconstructed ($VR_i$) vectors:
   $$\text{Fidelity} = \frac{1}{n} \sum_{i=1}^n \frac{\langle V_i, VR_i \rangle}{\|V_i\| \|VR_i\|} \times 100$$

2. **Percentage Root-mean-square Difference (PRD)**:
   $$PRD = \frac{\sqrt{\sum(V - VR)^2}}{\sqrt{\sum V^2}} \times 100$$

3. **Peak Signal-to-Noise Ratio (PSNR)**:
   $$PSNR = 20 \log_{10} \left( \frac{\text{MAX}_V}{\sqrt{\text{MSE}}} \right)$$

4. **Quality Score (QS)**: Single metric indicating the trade-off between CR and reconstruction quality:
   $$QS = \frac{CR}{PRD}$$

---

## 14. Butterworth Filter Selection & Performance Analysis

The study investigated different filter configurations to identify the optimal pre-processing filter. The **1st-order low-pass Butterworth filter with a Cutoff Frequency (CF) of 10 Hz** was chosen as it yields the best trade-off between CR, PRD, and Fidelity:

### 📊 Filter Comparison (Table 1)

| S.No. | Filter Order | Cutoff Frequency (CF) | Compression Ratio (CR) | PRD (%) | Fidelity (%) | PSNR (dB) | Quality Score (QS) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **1** | **10** | **12.37** | **4.71** | **99.89** | **39.17** | **2.63** |
| 2 | 2 | 10 | 11.49 | 4.72 | 99.89 | 38.89 | 2.43 |
| 3 | 1 | 20 | 13.40 | 5.52 | 99.85 | 39.25 | 2.43 |
| 4 | 3 | 30 | 17.14 | 6.98 | 99.76 | 38.97 | 2.45 |
| 5 | 4 | 50 | 15.91 | 7.95 | 99.68 | 38.44 | 2.00 |
| 6 | 4 | 100 | 14.52 | 8.32 | 99.65 | 37.96 | 1.74 |


## 15. Algorithm Comparisons & Study Limitations (Summary)

### 📊 Filter Comparison (Table 2)
Butterworth (QS = 2.63, PRD = 4.71%) outperforms Savitzky-Golay (QS = 2.47), Median (QS = 1.72), and Chebyshev (QS = 1.60) filters by maximizing reconstruction fidelity while removing noise.

### 📊 Decomposition comparison (Table 5)
* **KL Transform + TQWT** (QS = 2.63) outperforms **SVD + TQWT** (QS = 1.73), **ICA + TQWT** (QS = 1.78), and **Only TQWT** (QS = 1.78).
* It improves Quality Score by ~52% over SVD-based methods.

### 📊 Comparison with Standard DCT and KLT (Table 4)
Classic KLT (QS = 0.80, PRD = 19.67%) and DCT (QS = 0.97, PRD = 16.27%) exhibit severe degradation and distortion (PRD > 10% limit) at higher compression ratios. In contrast, the proposed method keeps PRD under 8%.

### ⚠️ Study Limitations & Future Directions
1. **Manual Parameter Tuning**: Parameters ($Q=4$, $r=1.2$, $J=6$, and $\gamma=1.5$) were set empirically. Future work aims to automate this using optimization algorithms (PSO, GWO, ABC).
2. **Single Dataset**: Validation is currently restricted to the PTB Diagnostic ECG Database.
3. **AI Integration**: Future research explores machine learning models (VAEs, GANs) to improve reconstruction robustness for noisy or missing segments.
