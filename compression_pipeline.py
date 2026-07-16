# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
from scipy import signal as scipy_signal

# ---------------------------------------------------------
# 1. Preprocessing Stage
# ---------------------------------------------------------
def preprocess_vcg(data, fs=1000.0, cutoff=10.0):
    """
    Applies a 1st-order low-pass Butterworth filter at 10 Hz cutoff frequency,
    and subtracts the mean of each lead to eliminate any DC offset.
    data: numpy array of shape (n, 3)
    """
    nyquist = fs / 2.0
    normalized_cutoff = cutoff / nyquist
    b, a = scipy_signal.butter(1, normalized_cutoff, btype='low')
    
    # Filter along each channel (axis=0 is time axis)
    filtered = scipy_signal.filtfilt(b, a, data, axis=0)
    
    # Subtract mean of each lead to completely eliminate DC offset
    centered = filtered - np.mean(filtered, axis=0, keepdims=True)
    return centered

# ---------------------------------------------------------
# 2. Discrete Karhunen-Loève (K-L) Expansion
# ---------------------------------------------------------
def kl_expansion(X):
    """
    Computes the K-L expansion for a 3 x n VCG matrix X.
    X: shape (3, n)
    Returns:
        Y: K-L coordinate shifted matrix of shape (3, n)
        V: Eigenvector matrix of shape (3, 3) (sorted descending by eigenvalues)
    """
    n = X.shape[1]
    # Covariance Matrix (3 x 3)
    C = (1.0 / (n - 1)) * (X @ X.T)
    
    # Eigenvalue Decomposition
    evals, V = np.linalg.eigh(C)
    
    # Sort eigenvalues and corresponding eigenvectors in descending order
    idx = np.argsort(evals)[::-1]
    V = V[:, idx]
    
    # Coordinate shift
    Y = V.T @ X
    return Y, V

def inverse_kl_expansion(Y, V):
    """
    Reconstructs the 3 x n matrix X from the K-L components Y and eigenvectors V.
    """
    return V @ Y

# ---------------------------------------------------------
# 3. Second Rotation Matrix Alignment
# ---------------------------------------------------------
def detect_qrs_pan_tompkins(signal, fs=1000.0):
    """
    Implements a robust Pan-Tompkins QRS detection algorithm on a 1D signal.
    """
    # 1. Bandpass filter: 5 to 15 Hz
    nyq = fs / 2.0
    b, a = scipy_signal.butter(3, [5.0/nyq, 15.0/nyq], btype='bandpass')
    bp_sig = scipy_signal.filtfilt(b, a, signal)
    
    # 2. Derivative filter
    deriv = np.diff(bp_sig)
    
    # 3. Squaring
    squared = deriv ** 2
    
    # 4. Moving Window Integration (150 ms window)
    window_size = int(0.15 * fs)
    mwi = np.convolve(squared, np.ones(window_size)/window_size, mode='same')
    
    # 5. Peak detection on integrated signal
    # Minimum distance of 300 ms between QRS complexes
    peaks, _ = scipy_signal.find_peaks(mwi, distance=int(0.3 * fs), height=0.1 * np.max(mwi))
    
    # Refine peak locations by finding local maximum in original signal magnitude
    refined_peaks = []
    for p in peaks:
        start = max(0, p - int(0.15 * fs))
        end = min(len(signal), p + int(0.05 * fs))
        if start < end:
            exact_p = start + np.argmax(signal[start:end])
            refined_peaks.append(exact_p)
            
    return np.array(refined_peaks)

def second_rotation_alignment(Y, qrs_peaks):
    """
    Performs second rotation step based on QRS detection and T-loop boundaries.
    Y: K-L projected signal, shape (3, n)
    qrs_peaks: indices of QRS peaks
    """
    n_samples = Y.shape[1]
    
    # 1. T-Loop Isolation: [qrs_peak + 100 ms, qrs_peak + 400 ms]
    t_loop_indices = []
    for p in qrs_peaks:
        start = p + 100
        end = p + 400
        if end <= n_samples:
            t_loop_indices.extend(range(start, end))
            
    # Fallback to entire signal if no peaks detected
    if len(t_loop_indices) == 0:
        t_loop_indices = list(range(n_samples))
        
    # Project T-loop onto primary principal plane (Y0, Y1)
    Y_plane = Y[0:2, t_loop_indices]
    
    # Find sample with longest spatial vector in Y0-Y1 plane
    norms = np.sum(Y_plane ** 2, axis=0)
    idx_max = np.argmax(norms)
    best_sample_idx = t_loop_indices[idx_max]
    
    # p-axis: unit vector along longest spatial vector in Y0-Y1 plane
    p_vec = Y[0:2, best_sample_idx]
    p_norm = np.linalg.norm(p_vec)
    if p_norm == 0:
        p_axis = np.array([1.0, 0.0])
    else:
        p_axis = p_vec / p_norm
    p1, p2 = p_axis[0], p_axis[1]
    
    # 2. QRS trajectory signed area to check counter-clockwise flow
    # QRS complex window: [qrs_peak - 50 ms, qrs_peak + 50 ms]
    area_sum = 0.0
    for p in qrs_peaks:
        start = max(0, p - 50)
        end = min(n_samples, p + 50)
        for t in range(start, end - 1):
            area_sum += Y[0, t] * Y[1, t+1] - Y[1, t] * Y[0, t+1]
            
    rot_sign = 1.0 if area_sum >= 0.0 else -1.0
    
    # q-axis perpendicular to p-axis in the plane
    if rot_sign >= 0.0:
        q_axis = np.array([-p2, p1])
        r3 = 1.0
    else:
        q_axis = np.array([p2, -p1])
        r3 = -1.0
        
    q1, q2 = q_axis[0], q_axis[1]
    
    # Build orthogonal 3D rotation matrix
    R_3D = np.array([
        [p1,  p2,  0.0],
        [q1,  q2,  0.0],
        [0.0, 0.0, r3]
    ])
    
    Z = R_3D @ Y
    return Z, R_3D

def inverse_second_rotation(Z, R_3D):
    """
    Reconstructs K-L components Y from aligned components Z using transpose of R_3D.
    """
    return R_3D.T @ Z

# ---------------------------------------------------------
# 4. Tunable Q-Factor Wavelet Transform (TQWT)
# ---------------------------------------------------------
def analysis_filter_bank(x: np.ndarray, n0: int, n1: int):
    n = x.shape[0]
    p = int((n - n1) / 2)
    t = int((n0 + n1 - n) / 2 - 1)
    s = int((n - n0) / 2)
    
    v = np.arange(start=1, stop=t + 1) / (t + 1) * np.pi
    transit_band = (1 + np.cos(v)) * np.sqrt(2 - np.cos(v)) / 2.0
    
    lp_subband = np.zeros(n0, dtype=x.dtype)
    lp_subband[0] = x[0]
    lp_subband[1 : p + 1] = x[1 : p + 1]
    lp_subband[1 + p : p + t + 1] = x[1 + p : p + t + 1] * transit_band
    lp_subband[n0 // 2] = 0
    lp_subband[n0 - p - t : n0 - p] = x[n - p - t : n - p] * np.flip(transit_band)
    lp_subband[n0 - p :] = x[n - p :]
    
    hp_subband = np.zeros(n1, dtype=x.dtype)
    hp_subband[0] = 0
    hp_subband[1 : t + 1] = x[1 + p : t + p + 1] * np.flip(transit_band)
    hp_subband[t + 1 : s + 1 + t] = x[p + t + 1 : p + t + s + 1]
    if n % 2 == 0:
        hp_subband[n1 // 2] = x[n // 2]
    hp_subband[n1 - t - s - 1 : n1 - t] = x[n - p - t - s - 1 : n - p - t]
    hp_subband[n1 - t : n1] = x[n - p - t : n - p] * transit_band
    
    return lp_subband, hp_subband

def synthesis_filter_bank(lp_subband: np.ndarray, hp_subband: np.ndarray, n: int) -> np.ndarray:
    n0 = lp_subband.shape[0]
    n1 = hp_subband.shape[0]
    p = int((n - n1) / 2)
    t = int((n0 + n1 - n) / 2 - 1)
    s = int((n - n0) / 2)
    
    v = np.arange(start=1, stop=t + 1) / (t + 1) * np.pi
    trans = (1 + np.cos(v)) * np.sqrt(2 - np.cos(v)) / 2.0
    
    y0 = np.zeros(n, dtype=complex)
    y0[0] = lp_subband[0]
    y0[1 : p + 1] = lp_subband[1 : p + 1]
    y0[1 + p : p + t + 1] = lp_subband[1 + p : p + t + 1] * trans
    y0[p + t + 1 : p + t + s + 1] = 0.0
    if n % 2 == 0:
        y0[n // 2] = 0.0
    y0[n - p - t - s : n - p - t] = 0.0
    y0[n - p - t : n - p] = lp_subband[n0 - p - t : n0 - p] * np.flip(trans)
    y0[n - p :] = lp_subband[n0 - p :]
    
    y1 = np.zeros(n, dtype=complex)
    y1[0] = 0.0
    y1[1 : p + 1] = 0.0
    y1[1 + p : t + p + 1] = hp_subband[1 : t + 1] * np.flip(trans)
    y1[p + t + 1 : p + t + s + 1] = hp_subband[t + 1 : s + 1 + t]
    if n % 2 == 0:
        y1[n // 2] = hp_subband[n1 // 2]
    y1[n - p - t - s - 1 : n - p - t] = hp_subband[n1 - t - s - 1 : n1 - t]
    y1[n - p - t : n - p] = hp_subband[n1 - t : n1] * trans
    y1[n - p : n] = 0.0
    
    return y0 + y1

def tqwt(x: np.ndarray, q: float = 4.0, redundancy: float = 1.2, stages: int = 6) -> list:
    if q < 1:
        raise ValueError("q must be >= 1!")
    if redundancy <= 1:
        raise ValueError("redundancy must be > 1!")
    if stages < 1:
        raise ValueError("stages must be a positive integer!")
    if x.shape[0] % 2 or len(x.shape) != 1:
        raise ValueError("Input signal x must be 1D and of even length!")
        
    x = np.asarray(x)
    beta = float(2 / (q + 1))
    alpha = float(1 - beta / redundancy)
    n = x.shape[0]
    
    # Check max stages
    max_num_stages = int(np.floor(np.log(beta * n / 8) / np.log(1 / alpha)))
    if stages > max_num_stages:
        stages = max_num_stages
        
    fft_of_x = np.fft.fft(x) / np.sqrt(n)
    w = []
    
    for subband_idx in range(1, stages + 1):
        n0 = 2 * int(round(alpha**subband_idx * n / 2))
        n1 = 2 * int(round(beta * alpha ** (subband_idx - 1) * n / 2))
        fft_of_x, w_subband = analysis_filter_bank(fft_of_x, n0, n1)
        w.append(np.fft.ifft(w_subband) * np.sqrt(len(w_subband)))
        
    w.append(np.fft.ifft(fft_of_x) * np.sqrt(len(fft_of_x)))
    return w

def itqwt(w: list, q: float = 4.0, redundancy: float = 1.2, n: int = 30000) -> np.ndarray:
    beta = 2.0 / (q + 1)
    alpha = 1.0 - beta / redundancy
    num_subbands = len(w)
    
    y = np.fft.fft(w[num_subbands - 1]) / np.sqrt(w[num_subbands - 1].shape[0])
    
    for subband_idx in reversed(range(num_subbands - 1)):
        W = np.fft.fft(w[subband_idx]) / np.sqrt(len(w[subband_idx]))
        m = 2 * int(round(alpha**subband_idx * n / 2))
        y = synthesis_filter_bank(y, W, m)
        
    return np.real_if_close(np.fft.ifft(y) * np.sqrt(y.shape[0]))

# ---------------------------------------------------------
# 5. Dead-Zone Quantization (DZQ) & Encoding
# ---------------------------------------------------------
def quantize_coefs(coefs_list, gamma=1.5, bins=128.0):
    """
    Quantizes TQWT coefficients using the adaptive dead-zone scheme.
    coefs_list: list of 1D numpy arrays of wavelet coefficients
    bins: number of bins to divide the coefficient range (defaults to 128.0 to ensure PRD < 10)
    Returns:
        quantized_list: list of integer arrays of quantized indices
        Th: computed scalar threshold
        Delta: computed scalar step size
    """
    # Flatten all coefficients to find absolute min and max
    flat_coefs = np.concatenate([np.real(c) for c in coefs_list])
    M = np.max(flat_coefs)
    N = np.min(flat_coefs)
    
    Th = (M - N) / float(bins)
    Delta = gamma * Th
    
    quantized_list = []
    for c in coefs_list:
        real_c = np.real(c)
        abs_c = np.abs(real_c)
        sign_c = np.sign(real_c)
        
        k = np.zeros_like(real_c, dtype=int)
        
        nonzero_mask = abs_c >= Th
        
        # k = 1 / -1
        k1_mask = nonzero_mask & (abs_c < 3.0 * Delta)
        k[k1_mask] = 1
        
        # k >= 2 / <= -2
        k2_mask = nonzero_mask & (abs_c >= 3.0 * Delta)
        k[k2_mask] = np.floor(abs_c[k2_mask] / (2.0 * Delta) + 0.5).astype(int)
        
        quantized_list.append(k * sign_c.astype(int))
        
    return quantized_list, Th, Delta

def dequantize_coefs(quantized_list, Delta, Th=None):
    """
    Reconstructs the coefficients from the quantized integer indices using midpoints.
    If Th is not provided, falls back to calculating Th assuming gamma=1.5 (Th = Delta / 1.5).
    """
    if Th is None:
        Th = Delta / 1.5
        
    dequantized_list = []
    for k in quantized_list:
        recon = np.zeros_like(k, dtype=float)
        # Midpoint of [Th, 3*Delta] for k = 1
        recon[k == 1] = 0.5 * (Th + 3.0 * Delta)
        recon[k == -1] = -0.5 * (Th + 3.0 * Delta)
        # Midpoint of [(2*k-1)*Delta, (2*k+1)*Delta] is 2*k*Delta for |k| >= 2
        mask_large = np.abs(k) >= 2
        recon[mask_large] = 2.0 * k[mask_large].astype(float) * Delta
        dequantized_list.append(recon)
    return dequantized_list

def rle_encode(arr):
    """
    Compresses a 1D integer array using Run-Length Encoding.
    Returns: list of (value, count) tuples.
    """
    if len(arr) == 0:
        return []
    
    values = []
    counts = []
    current_val = arr[0]
    current_count = 1
    for val in arr[1:]:
        if val == current_val:
            current_count += 1
        else:
            values.append(current_val)
            counts.append(current_count)
            current_val = val
            current_count = 1
    values.append(current_val)
    counts.append(current_count)
    return list(zip(values, counts))

def rle_decode(rle_data):
    """
    Decompresses RLE data back to a 1D integer array.
    """
    arr = []
    for val, count in rle_data:
        arr.extend([val] * count)
    return np.array(arr, dtype=int)

# ---------------------------------------------------------
# Full End-to-End Pipeline Functions
# ---------------------------------------------------------
def compress_vcg_signal(raw_data, fs=1000.0, q=4.0, redundancy=1.2, stages=6, gamma=1.5, bins=128.0):
    """
    Compresses a raw (N, 3) VCG signal.
    """
    # 1. Preprocess
    preprocessed = preprocess_vcg(raw_data, fs=fs)
    
    # Structured as 3 x n matrix
    X = preprocessed.T
    
    # 2. K-L Expansion
    Y, V = kl_expansion(X)
    
    # 3. Second Rotation Alignment
    # Run QRS detection on first KL component (leads containing most of the energy)
    norm_sig = np.linalg.norm(preprocessed, axis=1)
    qrs_peaks = detect_qrs_pan_tompkins(norm_sig, fs=fs)
    
    Z, R_3D = second_rotation_alignment(Y, qrs_peaks)
    
    # 4. TQWT Decomposition
    n_samples = Z.shape[1]
    z_flat = Z.flatten() # 1D vector of length 3n
    
    w_tqwt = tqwt(z_flat, q=q, redundancy=redundancy, stages=stages)
    
    # 5. DZQ Quantization
    w_quant, Th, Delta = quantize_coefs(w_tqwt, gamma=gamma, bins=bins)
    
    # 6. RLE Encode each subband
    encoded_subbands = [rle_encode(c) for c in w_quant]
    
    # Return compressed representation + metadata needed for reconstruction
    compressed_payload = {
        'encoded_subbands': encoded_subbands,
        'Th': Th,
        'Delta': Delta,
        'V': V,
        'R_3D': R_3D,
        'n_samples': n_samples,
        'q': q,
        'redundancy': redundancy,
        'stages': stages,
        'bins': bins
    }
    
    return compressed_payload, preprocessed

def decompress_vcg_signal(compressed_payload):
    """
    Decompresses the compressed payload to reconstruct the (N, 3) preprocessed VCG.
    """
    # Decode RLE
    w_quant = [rle_decode(rle) for rle in compressed_payload['encoded_subbands']]
    
    # Dequantize
    Th = compressed_payload.get('Th', None)
    w_dequant = dequantize_coefs(w_quant, compressed_payload['Delta'], Th)
    
    # Inverse TQWT
    n_flat = 3 * compressed_payload['n_samples']
    z_flat_recon = itqwt(w_dequant, 
                         q=compressed_payload['q'], 
                         redundancy=compressed_payload['redundancy'], 
                         n=n_flat)
    
    # Reshape back to 3 x n
    Z_recon = z_flat_recon.reshape(3, compressed_payload['n_samples'])
    
    # Inverse Second Rotation Alignment
    Y_recon = inverse_second_rotation(Z_recon, compressed_payload['R_3D'])
    
    # Inverse K-L Expansion
    X_recon = inverse_kl_expansion(Y_recon, compressed_payload['V'])
    
    # Transpose back to (N, 3)
    reconstructed = X_recon.T
    return reconstructed
