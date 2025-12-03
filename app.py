import streamlit as st
import os
from PIL import Image
from analysis import (
    ela, metadata_analysis, histogram_analysis, noise_map, jpeg_ghost,
    quant_table, cmfd, prnu, frequency_analysis, deepfake_detector, resampling_detector
)

# 1. Page Configuration
st.set_page_config(
    page_title="Veritas - Digital Forensics",
    page_icon="🔍",
    layout="wide"
)

# 2. Helper: Save Uploaded File to Disk (Required for some OpenCV algos)


def save_uploaded_file(uploaded_file):
    if not os.path.exists("temp"):
        os.makedirs("temp")
    file_path = os.path.join("temp", uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


# 3. Sidebar
st.sidebar.title("🔍 Veritas Tool")
st.sidebar.info("Upload a digital image to perform forensic analysis.")
uploaded_file = st.sidebar.file_uploader(
    "Choose an Image", type=["jpg", "jpeg", "png"])

# 4. Main Logic
if uploaded_file is not None:
    # Save file temporarily
    file_path = save_uploaded_file(uploaded_file)

    # Display Original
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(file_path, caption="Original Image", width="stretch")
    with col2:
        st.warning(f"Analyzing: {uploaded_file.name}")

    # 5. Analysis Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs(
        ["🕵️ ELA", "📋 Metadata", "📊 Histogram", "👻 Noise/Ghost", "💾 Quant Table",
         "🔄 CMFD", "📡 PRNU", "📈 Frequency", "😁 Deepfake", "🔀 Resampling", "ℹ️ Info", "🔬 Advanced"])

    # --- TAB 1: ELA ---
    with tab1:
        st.subheader("Advanced Error Level Analysis (ELA)")
        st.write(
            "The enhanced ELA module performs multi-quality ELA, block analysis, noise profiling, "
            "SSIM comparison, entropy, and more."
        )

        # ---------- User Inputs ----------
        quality = st.slider(
            label="ELA JPEG Quality",
            min_value=50,
            max_value=95,
            value=90,
            step=1,
            help="Select the JPEG recompression quality used for ELA processing (lower = stronger artifacts)."
        )
        error_scale = st.slider(
            label="ELA Error Scale",
            min_value=1,
            max_value=100,
            value=20,
            step=1,
            help="Amplify subtle compression differences to make edits more visible."
        )
        overlay_opacity = st.slider(
            label="ELA Overlay Opacity",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.05,
            help="Blend the ELA map on the original image for better visualization."
        )

        st.write(
            f"Selected JPEG quality: **{quality}**, Error Scale: **{error_scale}**, Overlay Opacity: **{overlay_opacity}**")

        # ---------- Run ELA ----------
        if st.button("Run Full ELA Analysis"):
            with st.spinner("Running Enhanced ELA Pipeline..."):
                try:
                    report = ela.forensic_analysis(
                        file_path,
                        qualities=[quality],
                        error_scale=error_scale,
                        overlay_opacity=overlay_opacity
                    )

                    # 1. Main ELA (Grayscale + Overlay)
                    st.subheader("📷 ELA Result")
                    col_ela1, col_ela2 = st.columns(2)
                    with col_ela1:
                        st.image(
                            report["ela_90"], caption=f"ELA Grayscale (Quality {quality})", width="stretch")
                    with col_ela2:
                        st.image(
                            report["ela_90_overlay"], caption=f"ELA Overlay (Quality {quality})", width="stretch")
                    st.json(report["ela_90_metrics"])

                    st.markdown("---")
                    st.subheader("📊 Block-Based ELA Statistics")
                    st.json(report["block_stats"])

                    # 2. Multi-quality ELA (overlays included)
                    st.markdown("---")
                    st.subheader("📉 Multi-Quality ELA Results")
                    for q, res in report["ela_multi_quality"].items():
                        st.write(f"**Quality {q}**")
                        col_multi1, col_multi2 = st.columns(2)
                        with col_multi1:
                            st.image(res["ela"], caption="ELA Grayscale",
                                     width="stretch")
                        with col_multi2:
                            st.image(res["overlay"], caption="ELA Overlay",
                                     width="stretch")
                        st.json(res["metrics"])

                    # 3. Supporting Maps
                    st.markdown("---")
                    st.subheader("🧭 Supporting Forensic Maps")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.image(report["noise_map"],
                                 caption="Noise Map", width="stretch")
                    with col_b:
                        st.image(
                            report["sharpness_map"], caption="Sharpness Map", width="stretch")
                    with col_c:
                        st.image(
                            report["entropy_map"], caption="Entropy Map", width="stretch")

                    # 4. SSIM
                    st.markdown("---")
                    st.subheader("📝 SSIM Map")
                    st.image(
                        report["ssim_img"], caption=f"SSIM Map (Score: {report['ssim_score']:.4f})", width="stretch")

                    # 5. Threshold Mask
                    st.markdown("---")
                    st.subheader("🎯 Threshold Mask")
                    st.image(report["threshold_mask"],
                             caption="High Error Regions", width="stretch")

                except Exception as e:
                    st.error(f"ELA Processing Error: {e}")

    # --- TAB 2: METADATA ---
    with tab2:
        st.subheader("🔍 Advanced Metadata Forensics")
        st.write(
            "Deep analysis of EXIF data, GPS coordinates, timestamps, software signatures, "
            "and file structure integrity. Detects metadata anomalies and tampering indicators."
        )

        if st.button("🚀 Extract & Analyze Metadata", type="primary"):
            with st.spinner("Analyzing metadata and file structure..."):
                try:
                    # Run full analysis
                    report = metadata_analysis.full_metadata_analysis(
                        file_path)

                    # ========== SUMMARY CARD ==========
                    st.markdown("---")
                    st.subheader("📊 Analysis Summary")

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        score = report["summary"]["authenticity_score"]
                        if score >= 80:
                            color = "🟢"
                        elif score >= 50:
                            color = "🟡"
                        else:
                            color = "🔴"
                        st.metric("Authenticity Score", f"{score}/100")
                        st.markdown(
                            f"### {color} **{report['summary']['verdict']}**")

                    with col2:
                        st.metric("Total Warnings",
                                  report["summary"]["total_warnings"])
                        st.metric("File Type", report["summary"]["file_type"])

                    with col3:
                        st.metric(
                            "Has EXIF", "✅ Yes" if report["summary"]["has_exif"] else "❌ No")
                        st.metric(
                            "Has GPS", "✅ Yes" if report["summary"]["has_gps"] else "❌ No")

                    with col4:
                        st.metric(
                            "Edited", "⚠️ Yes" if report["summary"]["edited"] else "✅ No")
                        file_size = report["metadata"]["basic_info"]["file_size_mb"]
                        st.metric("File Size", f"{file_size} MB")

                    # ========== ANOMALIES ==========
                    st.markdown("---")
                    st.subheader("⚠️ Anomaly Detection")

                    anomalies = report["anomalies"]

                    if anomalies["critical"]:
                        st.error("**🔴 Critical Issues**")
                        for issue in anomalies["critical"]:
                            st.markdown(f"- {issue}")

                    if anomalies["warning"]:
                        st.warning("**🟡 Warnings**")
                        for warning in anomalies["warning"]:
                            st.markdown(f"- {warning}")

                    if anomalies["info"]:
                        st.info("**ℹ️ Informational**")
                        for info in anomalies["info"]:
                            st.markdown(f"- {info}")

                    if not (anomalies["critical"] or anomalies["warning"] or anomalies["info"]):
                        st.success("✅ No significant anomalies detected")

                    # ========== BASIC INFO ==========
                    st.markdown("---")
                    st.subheader("📄 Basic File Information")

                    col_left, col_right = st.columns(2)

                    with col_left:
                        basic = report["metadata"]["basic_info"]
                        st.json({
                            "Filename": basic["filename"],
                            "Format": basic["format"],
                            "Dimensions": f"{basic['width']}x{basic['height']}",
                            "Megapixels": basic["megapixels"],
                            "Color Mode": basic["mode"],
                            "File Size (MB)": basic["file_size_mb"],
                            "File Size (Bytes)": basic["file_size_bytes"]
                        })

                    with col_right:
                        st.json({
                            "File Created": basic["file_created"],
                            "File Modified": basic["file_modified"],
                            "File Accessed": basic["file_accessed"]
                        })

                    # ========== CAMERA INFO ==========
                    if report["metadata"]["camera"]:
                        st.markdown("---")
                        st.subheader("📷 Camera Information")
                        st.json(report["metadata"]["camera"])

                    # ========== SOFTWARE INFO ==========
                    if report["metadata"]["software"]:
                        st.markdown("---")
                        st.subheader("💻 Software & Processing")
                        st.json(report["metadata"]["software"])

                        # Highlight if editing software detected
                        software_str = str(
                            report["metadata"]["software"]).lower()
                        editing_apps = [
                            "photoshop", "gimp", "lightroom", "paint.net", "affinity", "pixlr"]
                        if any(editor in software_str for editor in editing_apps):
                            st.warning(
                                "⚠️ Image editing software detected in metadata")

                    # ========== TIMESTAMPS ==========
                    if report["metadata"]["timestamps"]:
                        st.markdown("---")
                        st.subheader("🕐 Timestamp Information")
                        st.json(report["metadata"]["timestamps"])

                    # ========== GPS DATA ==========
                    if report["metadata"]["gps"]:
                        st.markdown("---")
                        st.subheader("🌍 GPS Location Data")

                        if "coordinates" in report["metadata"]["gps"]:
                            coords = report["metadata"]["gps"]["coordinates"]

                            col_gps1, col_gps2 = st.columns(2)
                            with col_gps1:
                                st.metric("Latitude", coords["latitude"])
                                st.metric("Longitude", coords["longitude"])

                            with col_gps2:
                                st.markdown(
                                    f"**[📍 View on Google Maps]({coords['google_maps']})**")
                                st.info("Click the link above to view location")

                            # Show map if coordinates are valid
                            if coords["latitude"] != 0 and coords["longitude"] != 0:
                                try:
                                    import pandas as pd
                                    map_data = pd.DataFrame({
                                        'lat': [coords["latitude"]],
                                        'lon': [coords["longitude"]]
                                    })
                                    st.map(map_data)
                                except Exception as map_error:
                                    st.warning(
                                        f"Could not display map: {map_error}")

                        # Show raw GPS data
                        with st.expander("📋 View Raw GPS Tags"):
                            gps_display = {
                                k: v for k, v in report["metadata"]["gps"].items() if k != "coordinates"}
                            if gps_display:
                                st.json(gps_display)
                            else:
                                st.info("Only coordinate data available")

                    # ========== EXIF DATA ==========
                    if report["metadata"]["exif"]:
                        st.markdown("---")
                        st.subheader("🔬 EXIF Data")

                        with st.expander("📋 View All EXIF Tags", expanded=False):
                            st.json(report["metadata"]["exif"])
                    else:
                        st.markdown("---")
                        st.warning("⚠️ No EXIF data found in image")

                    # ========== THUMBNAIL ==========
                    if report["metadata"]["thumbnail"].get("present"):
                        st.markdown("---")
                        st.subheader("🖼️ Embedded Thumbnail")
                        with st.expander("📋 View Thumbnail Metadata"):
                            st.json(report["metadata"]["thumbnail"])

                    # ========== FILE STRUCTURE ==========
                    st.markdown("---")
                    st.subheader("🔧 File Structure Analysis")

                    structure = report["file_structure"]

                    col_struct1, col_struct2 = st.columns(2)

                    with col_struct1:
                        st.markdown("**File Signature**")
                        st.json(structure["signature"])

                    with col_struct2:
                        st.markdown("**Integrity Hashes**")
                        st.code(
                            f"MD5: {structure['integrity']['md5']}", language=None)
                        st.code(
                            f"SHA256: {structure['integrity']['sha256']}", language=None)

                    # JPEG Structure
                    if structure["jpeg_structure"]:
                        st.markdown("---")
                        st.markdown("**JPEG Structure Analysis**")
                        jpeg_info = structure["jpeg_structure"]

                        col_jpeg1, col_jpeg2 = st.columns(2)
                        with col_jpeg1:
                            st.metric("Total Segments",
                                      jpeg_info["total_segments"])
                            st.metric("Has Thumbnail",
                                      "✅ Yes" if jpeg_info["has_embedded_thumbnail"] else "❌ No")

                        with col_jpeg2:
                            double_comp = jpeg_info["double_compressed_indicator"]
                            if double_comp:
                                st.warning(
                                    "⚠️ Multiple Quantization Tables Detected")
                                st.markdown(
                                    "*May indicate recompression/editing*")
                            else:
                                st.success("✅ Single Compression Detected")

                        with st.expander("📋 View JPEG Segment Sequence"):
                            st.code(
                                ", ".join(jpeg_info["segment_sequence"]), language=None)

                    # File structure warnings
                    if structure["warnings"]:
                        st.markdown("---")
                        st.warning("**⚠️ File Structure Warnings**")
                        for warning in structure["warnings"]:
                            st.markdown(f"- {warning}")

                    # ========== EXPORT OPTIONS ==========
                    st.markdown("---")
                    st.subheader("💾 Export Report")

                    col_export1, col_export2 = st.columns(2)

                    with col_export1:
                        # Convert report to JSON string
                        import json
                        json_str = json.dumps(report, indent=2, default=str)

                        st.download_button(
                            label="📥 Download JSON Report",
                            data=json_str,
                            file_name=f"metadata_report_{report['metadata']['basic_info']['filename']}.json",
                            mime="application/json",
                            help="Download complete metadata analysis as JSON file"
                        )

                    with col_export2:
                        # Create summary text
                        summary_text = f"""Metadata Analysis Report
    ========================
    File: {report['metadata']['basic_info']['filename']}
    Authenticity Score: {report['summary']['authenticity_score']}/100
    Verdict: {report['summary']['verdict']}
    Total Warnings: {report['summary']['total_warnings']}

    Anomalies:
    - Critical Issues: {len(anomalies['critical'])}
    - Warnings: {len(anomalies['warning'])}
    - Informational: {len(anomalies['info'])}

    File Info:
    - Format: {report['summary']['file_type']}
    - Size: {report['metadata']['basic_info']['file_size_mb']} MB
    - Dimensions: {report['metadata']['basic_info']['width']}x{report['metadata']['basic_info']['height']}
    - Has EXIF: {'Yes' if report['summary']['has_exif'] else 'No'}
    - Has GPS: {'Yes' if report['summary']['has_gps'] else 'No'}
    - Edited: {'Yes' if report['summary']['edited'] else 'No'}
    """

                        st.download_button(
                            label="📋 Download Summary Text",
                            data=summary_text,
                            file_name=f"metadata_summary_{report['metadata']['basic_info']['filename']}.txt",
                            mime="text/plain",
                            help="Download quick summary as text file"
                        )

                except Exception as e:
                    st.error(f"❌ Metadata Analysis Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

    # --- TAB 3: HISTOGRAM ---
    with tab3:
        st.subheader("Histogram Analysis")
        if st.button("Generate Histogram"):
            with st.spinner("Processing..."):
                hist_path = histogram_analysis.generate_histogram(file_path)
                if hist_path:
                    st.image(hist_path, caption="Histogram Analysis",
                             width="stretch")
                else:
                    st.error("Failed to generate histogram.")

    # --- TAB 4: NOISE & GHOST ---
    with tab4:
        st.subheader("Noise Map & JPEG Ghost")
        col_noise, col_ghost = st.columns(2)

        with col_noise:
            if st.button("Generate Noise Map"):
                with st.spinner("Processing..."):
                    noise_img = noise_map.generate_noise_map(file_path)
                    if noise_img:
                        st.image(noise_img, caption="Noise Map",
                                 width="stretch")

        with col_ghost:
            if st.button("Detect JPEG Ghost"):
                with st.spinner("Processing..."):
                    ghost_img = jpeg_ghost.detect_ghost(file_path)
                    if ghost_img:
                        st.image(ghost_img, caption="JPEG Ghost Detection",
                                 width="stretch")

    # --- TAB 5: QUANTIZATION TABLE ---
    with tab5:
        st.subheader("JPEG Quantization Table Analysis")
        if st.button("Analyze Quantization Tables"):
            with st.spinner("Processing..."):
                result = quant_table.analyze_quantization_table(file_path)
                st.json(result)

    # --- TAB 6: CMFD ---
    with tab6:
        st.subheader("Copy-Move Forgery Detection")
        if st.button("Run CMFD Analysis"):
            with st.spinner("Processing..."):
                result = cmfd.detect_copy_move(file_path)
                if isinstance(result, dict) and 'result' in result:
                    st.info(result['result'])
                else:
                    st.json(result)

    # --- TAB 7: PRNU ---
    with tab7:
        st.subheader("PRNU - Sensor Fingerprint Analysis")
        if st.button("Analyze PRNU"):
            with st.spinner("Processing..."):
                result = prnu.analyze_prnu(file_path)
                st.json(result)

    # --- TAB 8: FREQUENCY ANALYSIS ---
    with tab8:
        st.subheader("Frequency Domain Analysis")
        col_fft, col_dct = st.columns(2)

        with col_fft:
            if st.button("FFT Analysis"):
                with st.spinner("Processing..."):
                    result = frequency_analysis.analyze_frequency_domain(
                        file_path)
                    st.json(result)

        with col_dct:
            if st.button("DCT Anomalies"):
                with st.spinner("Processing..."):
                    result = frequency_analysis.detect_dct_anomalies(file_path)
                    st.json(result)

    # --- TAB 9: DEEPFAKE DETECTION ---
    with tab9:
        st.subheader("Deepfake & GAN Detection")
        col_artifacts, col_gan = st.columns(2)

        with col_artifacts:
            if st.button("Detect GAN Artifacts"):
                with st.spinner("Processing..."):
                    result = deepfake_detector.detect_deepfake_artifacts(
                        file_path)
                    st.json(result)

        with col_gan:
            if st.button("Detect GAN Fingerprint"):
                with st.spinner("Processing..."):
                    result = deepfake_detector.detect_gan_fingerprint(
                        file_path)
                    st.json(result)

    # --- TAB 10: RESAMPLING DETECTION ---
    with tab10:
        st.subheader("Resampling & Interpolation Detection")
        col_resample, col_interp = st.columns(2)

        with col_resample:
            if st.button("Detect Resampling"):
                with st.spinner("Processing..."):
                    result = resampling_detector.detect_resampling(file_path)
                    st.json(result)

        with col_interp:
            if st.button("Identify Interpolation Method"):
                with st.spinner("Processing..."):
                    result = resampling_detector.detect_interpolation_method(
                        file_path)
                    st.json(result)

    # --- TAB 11: INFO ---
    with tab11:
        st.subheader("About Veritas")
        st.markdown("""
        **Veritas** is a comprehensive digital forensics tool designed to detect image forgeries and tampering.
        
        ### Complete Analysis Methods:
        - **ELA**: Error Level Analysis highlights compression artifacts
        - **Metadata**: Extract and analyze EXIF data
        - **Histogram**: Analyze color distribution patterns
        - **Noise Map**: Detect noise inconsistencies
        - **JPEG Ghost**: Multi-level compression artifact detection
        - **Quantization Table**: Analyze JPEG compression tables
        - **CMFD**: Copy-Move Forgery Detection
        - **PRNU**: Photo Response Non-Uniformity (sensor fingerprint)
        - **Frequency Analysis**: FFT/DCT-based tampering detection
        - **Deepfake Detection**: GAN and deepfake artifact classification
        - **Resampling Detection**: Identify image resizing and interpolation methods
        """)

    # --- TAB 12: ADVANCED ---
    with tab12:
        st.subheader("Advanced Tools & Batch Analysis")
        st.info("Advanced features (batch processing, report generation) coming soon")

        if st.checkbox("Run All Analyses"):
            st.warning("Batch processing may take several minutes...")
            if st.button("Start Comprehensive Analysis"):
                st.info(
                    "Comprehensive multi-technique analysis pending implementation")

else:
    st.markdown("### Welcome to Veritas 🔍")
    st.markdown("""
    **Digital Forensics Image Analysis Tool**
    
    This tool allows you to analyze images for forgeries using advanced forensic techniques:
    * **Error Level Analysis (ELA)** - Highlights compression differences
    * **Metadata Extraction** - Examines EXIF and image properties
    * **Noise Analysis** - Detects noise inconsistencies
    * **Copy-Move Detection** - Finds duplicated regions
    
    **How to use:**
    1. Upload an image using the sidebar
    2. Select an analysis technique from the tabs
    3. Review the results
    """)
