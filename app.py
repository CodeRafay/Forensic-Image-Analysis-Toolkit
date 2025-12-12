import streamlit as st
import os
from analysis import (
    ela, metadata_analysis, histogram_analysis, noise_map, jpeg_ghost,
    quant_table, cmfd, prnu, frequency_analysis, deepfake_detector, resampling_detector,
    steganography_detection, hash_verification
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


# 3. Helper: Load Technique Description
def load_description(technique_name):
    """
    Load markdown description for a forensic technique.

    Args:
        technique_name: Name of technique (e.g., 'ELA', 'Metadata', 'FFT')

    Returns:
        String containing markdown content, or error message if not found
    """
    description_file = os.path.join("Descriptions", f"{technique_name}.md")

    if os.path.exists(description_file):
        try:
            with open(description_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error loading description: {str(e)}"
    else:
        return f"Description file not found: {description_file}"


# 4. Technique Description Mapping
TECHNIQUES = {
    "🕵️ ELA": "ELA",
    "📋 Metadata": "Metadata",
    "📊 Histogram": "Histogram",
    "👻 Noise/Ghost": "Noise_Ghost",
    "💾 Quantization": "Quantization",
    "🔄 CMFD": "CMFD",
    "📡 PRNU": "PRNU",
    "📈 Frequency": "Frequency",
    "😁 Deepfake": "Deepfake",
    "🔀 Resampling": "Resampling",
    "🔐 Steganography": "Steganography",
    "🔑 Hash Verify": "Hash_Verification",
}


# 5. Default Sample Image Path
DEFAULT_SAMPLE_IMAGE = os.path.join(
    "assets", "sample images", "sampleImg.jpeg")

# 6. Sidebar - File Upload Section
st.sidebar.title("🔍 Veritas Tool")
st.sidebar.info(
    "Upload a digital image to perform forensic analysis, or test with the default sample image.")
uploaded_file = st.sidebar.file_uploader(
    "Choose an Image", type=["jpg", "jpeg", "png"])

# Show info about default sample
if uploaded_file is None and os.path.exists(DEFAULT_SAMPLE_IMAGE):
    st.sidebar.success("📸 Using default sample image for testing")
    st.sidebar.caption("Upload your own image above to analyze it instead")

# 7. Sidebar - Technique Descriptions Section
st.sidebar.markdown("---")
st.sidebar.subheader("📚 Technique Descriptions")
st.sidebar.caption("Learn about each forensic analysis method")

# Create columns for description buttons
desc_cols = st.sidebar.columns(2)
selected_description = None

for idx, (display_name, technique_key) in enumerate(TECHNIQUES.items()):
    col = desc_cols[idx % 2]
    if col.button(display_name, key=f"desc_{technique_key}", use_container_width=True):
        selected_description = technique_key
        st.session_state.selected_description = technique_key

# Check session state for selected description
if "selected_description" in st.session_state:
    selected_description = st.session_state.selected_description

# Display Technique Description if selected
if selected_description is not None:
    st.markdown("---")
    st.markdown(f"## 📖 {selected_description} Description")

    description_content = load_description(selected_description)
    st.markdown(description_content)

    st.markdown("---")

# 8. Main Logic - Determine which image to use
if uploaded_file is not None:
    # User uploaded a file
    file_path = save_uploaded_file(uploaded_file)
    image_name = uploaded_file.name
    is_sample = False
elif os.path.exists(DEFAULT_SAMPLE_IMAGE):
    # Use default sample image
    file_path = DEFAULT_SAMPLE_IMAGE
    image_name = "Sample Image (Default)"
    is_sample = True
else:
    # No image available
    file_path = None
    image_name = None
    is_sample = False

# Process the image if available
if file_path is not None:

    # Display Original
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(file_path, caption="Original Image", width="stretch")
    with col2:
        if is_sample:
            st.info(f"📸 Analyzing: {image_name}")
            st.caption(
                "This is a sample image loaded by default. Upload your own image in the sidebar to analyze it.")
        else:
            st.warning(f"Analyzing: {image_name}")

    # 5. Analysis Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14 = st.tabs(
        ["🕵️ ELA", "📋 Metadata", "📊 Histogram", "👻 Noise/Ghost", "💾 Quant Table",
         "🔄 CMFD", "📡 PRNU", "📈 Frequency", "😁 Deepfake", "🔀 Resampling", 
         "🔐 Steganography", "🔑 Hash Verify", "ℹ️ Info", "🔬 Advanced"])

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
        st.subheader("📊 Advanced Histogram Analysis")
        st.write(
            "RGB histogram analysis with statistical forensics to detect manipulation indicators "
            "such as artificial gaps (comb patterns), clipping, and unusual distributions."
        )

        if st.button("🚀 Generate Histogram Analysis", type="primary"):
            with st.spinner("Analyzing color distribution patterns..."):
                try:
                    result = histogram_analysis.generate_histogram(file_path)

                    if result['status'] == 'success':
                        # Display histogram image
                        st.markdown("---")
                        st.subheader("📈 RGB Histogram")
                        st.image(
                            result['histogram_path'], caption="Histogram Analysis", width='stretch')

                        # Statistics summary cards
                        st.markdown("---")
                        st.subheader("📊 Statistical Summary")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.markdown("**🔴 Red Channel**")
                            red_stats = result['statistics']['red']
                            st.metric("Mean", f"{red_stats['mean']:.2f}")
                            st.metric("Std Dev", f"{red_stats['std']:.2f}")
                            st.metric(
                                "Range", f"{red_stats['min']:.0f} - {red_stats['max']:.0f}")
                            st.metric("Median", f"{red_stats['median']:.2f}")

                        with col2:
                            st.markdown("**🟢 Green Channel**")
                            green_stats = result['statistics']['green']
                            st.metric("Mean", f"{green_stats['mean']:.2f}")
                            st.metric("Std Dev", f"{green_stats['std']:.2f}")
                            st.metric(
                                "Range", f"{green_stats['min']:.0f} - {green_stats['max']:.0f}")
                            st.metric("Median", f"{green_stats['median']:.2f}")

                        with col3:
                            st.markdown("**🔵 Blue Channel**")
                            blue_stats = result['statistics']['blue']
                            st.metric("Mean", f"{blue_stats['mean']:.2f}")
                            st.metric("Std Dev", f"{blue_stats['std']:.2f}")
                            st.metric(
                                "Range", f"{blue_stats['min']:.0f} - {blue_stats['max']:.0f}")
                            st.metric("Median", f"{blue_stats['median']:.2f}")

                        # Warnings section
                        if result['warnings']:
                            st.markdown("---")
                            st.subheader("⚠️ Detected Anomalies")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")
                        else:
                            st.markdown("---")
                            st.success("✅ No histogram anomalies detected")

                        # Interpretation
                        st.markdown("---")
                        st.subheader("💡 Interpretation")
                        st.info(result['interpretation'])

                        # Raw data expander
                        with st.expander("📋 View Raw Statistics"):
                            st.json(result['statistics'])

                    else:
                        st.error(
                            f"❌ Analysis Error: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ Histogram Analysis Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

    # --- TAB 4: NOISE & GHOST ---
    with tab4:
        st.subheader("👻 Noise Analysis & JPEG Ghost Detection")
        st.write(
            "Detect tampering through noise inconsistencies and compression artifacts. "
            "Authentic images have uniform noise patterns; manipulated regions show noise discrepancies."
        )

        # Noise Map Section
        st.markdown("---")
        st.markdown("### 🔬 Noise Map Analysis")
        st.write(
            "Extract and analyze high-frequency noise patterns to detect inconsistencies")

        if st.button("🚀 Generate Noise Map", type="primary", key="noise_btn"):
            with st.spinner("Extracting noise patterns..."):
                try:
                    result = noise_map.generate_noise_map(file_path)

                    if result['status'] == 'success':
                        # Display noise map
                        st.image(
                            result['noise_map_path'], caption="Noise Map (High-Frequency Components)", width='stretch')

                        # Metrics display
                        st.markdown("---")
                        st.subheader("📊 Noise Metrics")

                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Channel Variance**")
                            variance = result['metrics']['channel_noise_variance']
                            st.metric("Red Channel", f"{variance['red']:.2f}")
                            st.metric("Green Channel",
                                      f"{variance['green']:.2f}")
                            st.metric("Blue Channel",
                                      f"{variance['blue']:.2f}")

                        with col2:
                            st.markdown("**Consistency Analysis**")
                            st.metric(
                                "Overall Variance", f"{result['metrics']['overall_variance']:.2f}")
                            st.metric(
                                "Block Variance Std", f"{result['metrics']['block_variance_std']:.2f}")
                            st.metric("Blocks Analyzed",
                                      result['metrics']['blocks_analyzed'])

                        # Warnings
                        if result['warnings']:
                            st.markdown("---")
                            st.subheader("⚠️ Detected Issues")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")
                        else:
                            st.success("✅ Noise pattern appears consistent")

                        # Interpretation
                        st.markdown("---")
                        st.info(f"💡 {result['interpretation']}")

                    else:
                        st.error(
                            f"❌ Error: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ Noise Analysis Error: {str(e)}")

        # JPEG Ghost Section
        st.markdown("---")
        st.markdown("---")
        st.markdown("### 👻 JPEG Ghost Detection")
        st.write(
            "Multi-quality compression analysis to estimate last save quality and detect re-editing")

        if st.button("🚀 Detect JPEG Ghost", type="primary", key="ghost_btn"):
            with st.spinner("Analyzing compression history..."):
                try:
                    result = jpeg_ghost.detect_jpeg_ghost(file_path)

                    if result['status'] == 'success':
                        # Display combined ghost visualization
                        if result['combined_ghost_path']:
                            st.image(
                                result['combined_ghost_path'], caption="JPEG Ghost Analysis (Multiple Quality Levels)", width='stretch')

                        # Quality estimation results
                        st.markdown("---")
                        st.subheader("📊 Quality Estimation")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric("Estimated Last Save Quality",
                                      f"{result['estimated_last_save_quality']}")

                        with col2:
                            confidence = result['quality_confidence']
                            color = "🟢" if confidence == 'high' else "🟡"
                            st.metric("Confidence",
                                      f"{color} {confidence.upper()}")

                        with col3:
                            min_score = min(
                                result['difference_scores'].values())
                            st.metric("Min Difference Score",
                                      f"{min_score:.2f}")

                        # Difference scores by quality
                        st.markdown("---")
                        st.subheader("📈 Difference Scores by Quality")
                        st.write(
                            "Lower scores indicate quality closer to original compression")

                        import pandas as pd
                        df_scores = pd.DataFrame([
                            {"Quality Level": q, "Difference Score": score}
                            for q, score in sorted(result['difference_scores'].items())
                        ])
                        st.dataframe(df_scores, width='stretch')

                        # Warnings
                        if result['warnings']:
                            st.markdown("---")
                            st.subheader("⚠️ Detected Issues")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")
                        else:
                            st.success("✅ No compression anomalies detected")

                        # Interpretation
                        st.markdown("---")
                        st.info(f"💡 {result['interpretation']}")

                    else:
                        st.error(
                            f"❌ Error: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ JPEG Ghost Error: {str(e)}")

    # --- TAB 5: QUANTIZATION TABLE ---
    with tab5:
        st.subheader("💾 JPEG Quantization Table Analysis")
        st.write(
            "Analyze JPEG quantization tables to identify compression software, "
            "estimate quality settings, and detect non-standard table modifications."
        )

        if st.button("🚀 Analyze Quantization Tables", type="primary"):
            with st.spinner("Extracting and analyzing Q-tables..."):
                try:
                    result = quant_table.analyze_quantization_table(file_path)

                    if result['status'] == 'success':
                        # Quality estimation
                        st.markdown("---")
                        st.subheader("📊 Quality Assessment")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            quality = result.get(
                                'estimated_quality', 'Unknown')
                            st.metric("Estimated Quality", quality)

                        with col2:
                            tables_count = result.get('tables_found', 0)
                            st.metric("Tables Found", tables_count)

                        with col3:
                            is_standard = result.get(
                                'uses_standard_tables', 'Unknown')
                            indicator = "✅" if is_standard else "⚠️"
                            st.metric("Standard Tables",
                                      f"{indicator} {is_standard}")

                        # Table details
                        if 'tables' in result:
                            st.markdown("---")
                            st.subheader("🔍 Quantization Table Details")

                            for table_id, table_data in result['tables'].items():
                                with st.expander(f"📋 Table {table_id}"):
                                    # Display as 8x8 matrix
                                    import numpy as np
                                    table_array = np.array(
                                        table_data).reshape(8, 8)

                                    # Format as DataFrame for better display
                                    import pandas as pd
                                    df_table = pd.DataFrame(table_array)
                                    st.dataframe(
                                        df_table, width='stretch')

                                    st.caption(
                                        "Lower values = higher quality | Higher values = more compression")

                        # Warnings
                        if result.get('warnings'):
                            st.markdown("---")
                            st.subheader("⚠️ Detected Issues")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")
                        else:
                            st.success("✅ No Q-table anomalies detected")

                        # Interpretation
                        if result.get('interpretation'):
                            st.markdown("---")
                            st.info(f"💡 {result['interpretation']}")

                        # Raw data
                        with st.expander("📋 View Raw Analysis Data"):
                            st.json(result)

                    else:
                        st.error(
                            f"❌ Analysis Error: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ Q-Table Analysis Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

    # --- TAB 6: CMFD ---
    with tab6:
        st.subheader("🔄 Copy-Move Forgery Detection (CMFD)")
        st.write(
            "Detect duplicated regions within the image using DCT-based block matching. "
            "This technique identifies areas that have been copied and pasted to conceal or clone content."
        )

        # Parameter controls
        with st.expander("⚙️ Advanced Parameters"):
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                block_size = st.slider(
                    "Block Size", 8, 32, 16, 4, help="Size of blocks for matching (larger = faster but less precise)")
            with col_p2:
                threshold = st.slider(
                    "Similarity Threshold", 0.5, 0.99, 0.9, 0.05, help="Higher = stricter matching")

        if st.button("🚀 Run CMFD Analysis", type="primary"):
            with st.spinner("Analyzing for copy-move forgery... This may take a minute..."):
                try:
                    result = cmfd.detect_copy_move(
                        file_path, block_size=block_size, threshold=threshold)

                    if result['status'] == 'success':
                        # Display result image
                        st.markdown("---")
                        st.subheader("🖼️ Detection Result")
                        st.image(result['results']['result_image_path'],
                                 caption="Copy-Move Detection (Green/Red: Matched regions | Lines: Connections)",
                                 width='stretch')

                        # Analysis metrics
                        st.markdown("---")
                        st.subheader("📊 Analysis Metrics")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric(
                                "Blocks Analyzed", f"{result['results']['total_blocks_analyzed']:,}")

                        with col2:
                            matches = result['results']['matches_found']
                            color = "🔴" if matches > 20 else (
                                "🟡" if matches > 5 else "🟢")
                            st.metric("Matches Found", f"{color} {matches}")

                        with col3:
                            st.metric("Match Groups",
                                      result['results']['match_groups'])

                        # Parameters used
                        st.markdown("---")
                        st.subheader("⚙️ Parameters Used")
                        col_param1, col_param2, col_param3 = st.columns(3)
                        with col_param1:
                            st.metric(
                                "Block Size", f"{result['parameters']['block_size']}x{result['parameters']['block_size']}")
                        with col_param2:
                            st.metric(
                                "Threshold", result['parameters']['threshold'])
                        with col_param3:
                            st.metric("Min Distance",
                                      result['parameters']['min_distance'])

                        # Match details
                        if result.get('matches') and len(result['matches']) > 0:
                            st.markdown("---")
                            st.subheader("🔍 Top Matches")

                            import pandas as pd
                            match_data = []
                            for i, match in enumerate(result['matches'][:10], 1):
                                match_data.append({
                                    "#": i,
                                    "Block 1": f"({match['block1'][0]}, {match['block1'][1]})",
                                    "Block 2": f"({match['block2'][0]}, {match['block2'][1]})",
                                    "Similarity": f"{match['similarity']:.4f}"
                                })

                            df_matches = pd.DataFrame(match_data)
                            st.dataframe(df_matches, width='stretch')

                        # Warnings
                        if result.get('warnings'):
                            st.markdown("---")
                            st.subheader("⚠️ Detected Issues")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")
                        else:
                            st.success("✅ No copy-move forgery detected")

                        # Interpretation
                        st.markdown("---")
                        st.info(f"💡 {result['interpretation']}")

                        # Raw data
                        with st.expander("📋 View Raw Analysis Data"):
                            st.json(result)

                    else:
                        st.error(
                            f"❌ Analysis Error: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ CMFD Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

    # --- TAB 7: PRNU ---
    with tab7:
        st.subheader("📡 PRNU - Sensor Fingerprint Analysis")
        st.write(
            "Extract and analyze Photo Response Non-Uniformity (PRNU) patterns - "
            "unique sensor fingerprints that can identify the camera or detect spliced regions."
        )

        # Optional reference image
        st.markdown("### 📂 Optional: Reference Image")
        st.write(
            "Upload a reference image from the same camera for correlation analysis")
        reference_file = st.file_uploader("Reference Image (Optional)", type=[
                                          "jpg", "jpeg", "png"], key="prnu_ref")

        reference_path = None
        if reference_file:
            reference_path = save_uploaded_file(reference_file)
            st.success(f"✅ Reference image loaded: {reference_file.name}")

        if st.button("🚀 Analyze PRNU", type="primary"):
            with st.spinner("Extracting sensor fingerprint..."):
                try:
                    result = prnu.analyze_prnu(
                        file_path, reference_image_path=reference_path)

                    if result['status'] == 'success':
                        # Display PRNU pattern if available
                        if result.get('prnu_pattern_path'):
                            st.markdown("---")
                            st.subheader("🖼️ PRNU Pattern Visualization")
                            st.image(result['prnu_pattern_path'],
                                     caption="Sensor Noise Pattern (PRNU)",
                                     width='stretch')

                        # Pattern strength metrics
                        st.markdown("---")
                        st.subheader("📊 Pattern Strength Analysis")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            strength = result['metrics'].get(
                                'pattern_strength', 0)
                            color = "🟢" if strength > 5 else (
                                "🟡" if strength > 2 else "🔴")
                            st.metric("Pattern Strength",
                                      f"{color} {strength:.4f}")

                        with col2:
                            consistency = result['metrics'].get(
                                'variance_consistency', 0)
                            st.metric("Variance Consistency",
                                      f"{consistency:.4f}")

                        with col3:
                            blocks = result['metrics'].get(
                                'blocks_analyzed', 0)
                            st.metric("Blocks Analyzed", blocks)

                        # Correlation results (if reference provided)
                        if result.get('correlation_analysis'):
                            st.markdown("---")
                            st.subheader("🔗 Reference Correlation Analysis")

                            corr = result['correlation_analysis']
                            col_corr1, col_corr2 = st.columns(2)

                            with col_corr1:
                                correlation = corr.get('correlation', 0)
                                color = "🟢" if correlation > 0.7 else (
                                    "🟡" if correlation > 0.4 else "🔴")
                                st.metric("Correlation Coefficient",
                                          f"{color} {correlation:.4f}")

                            with col_corr2:
                                likelihood = corr.get(
                                    'same_camera_likelihood', 'Unknown')
                                st.metric("Same Camera Likelihood", likelihood)

                            st.info(
                                "💡 High correlation (>0.7) suggests same camera source. "
                                "Low correlation may indicate different camera or spliced regions."
                            )

                        # Warnings
                        if result.get('warnings'):
                            st.markdown("---")
                            st.subheader("⚠️ Detected Issues")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")
                        else:
                            st.success("✅ PRNU pattern appears consistent")

                        # Interpretation
                        if result.get('interpretation'):
                            st.markdown("---")
                            st.info(f"💡 {result['interpretation']}")

                        # Raw data
                        with st.expander("📋 View Raw Analysis Data"):
                            st.json(result)

                    else:
                        st.error(
                            f"❌ Analysis Error: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ PRNU Analysis Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

    # --- TAB 8: FREQUENCY ANALYSIS ---
    with tab8:
        st.subheader("📈 Frequency Domain Analysis")
        st.write(
            "Analyze image in frequency domain using FFT and DCT transforms to detect "
            "tampering artifacts, periodic patterns, and anomalies invisible in spatial domain."
        )

        # FFT Analysis Section
        st.markdown("---")
        st.markdown("### 🌊 FFT (Fast Fourier Transform) Analysis")
        st.write(
            "Analyzes the image's frequency patterns - like looking at the 'fingerprint' of how details are distributed. "
            "Edited images often have unnatural frequency patterns."
        )

        if st.button("🚀 Run FFT Analysis", type="primary", key="fft_btn"):
            with st.spinner("Computing FFT spectrum..."):
                try:
                    result = frequency_analysis.analyze_frequency_domain(
                        file_path)

                    if result.get('status') == 'success':
                        # Overall verdict
                        st.markdown("---")
                        st.subheader("🎯 Overall Assessment")

                        col_verdict1, col_verdict2, col_verdict3 = st.columns(
                            3)

                        with col_verdict1:
                            score = result['authenticity_score']
                            if score >= 80:
                                color = "🟢"
                            elif score >= 60:
                                color = "🟡"
                            else:
                                color = "🔴"
                            st.metric("Authenticity Score",
                                      f"{color} {score}/100")

                        with col_verdict2:
                            risk = result['risk_level']
                            risk_color = "🟢" if risk == "Low" else (
                                "🟡" if risk == "Medium" else "🔴")
                            st.metric("Risk Level", f"{risk_color} {risk}")

                        with col_verdict3:
                            st.metric("Status", result['verdict'][:20] + "...")

                        st.info(f"**Verdict:** {result['verdict']}")

                        # Display spectrum visualization
                        if result.get('magnitude_spectrum_path'):
                            st.markdown("---")
                            st.subheader("📊 Frequency Spectrum Visualization")
                            st.image(result['magnitude_spectrum_path'],
                                     caption="FFT Magnitude Spectrum - Shows how image details are distributed",
                                     width='stretch')
                            st.caption(
                                "💡 **How to read this:** Bright spots in the center = smooth areas | Bright outer regions = sharp edges and details")

                        # User-friendly metrics
                        st.markdown("---")
                        st.subheader("📈 What We Found")

                        metrics = result['metrics']
                        col_m1, col_m2, col_m3 = st.columns(3)

                        with col_m1:
                            detail_pct = metrics['high_frequency_energy_percentage']
                            st.metric("Fine Details", f"{detail_pct:.1f}%")
                            if detail_pct < 10:
                                st.caption("🔵 Low (smooth image)")
                            elif detail_pct < 30:
                                st.caption("🟢 Normal range")
                            else:
                                st.caption("🟡 High (very sharp)")

                        with col_m2:
                            consistency = metrics['phase_consistency_score']
                            st.metric("Pattern Consistency",
                                      f"{consistency:.1f}/10")
                            if consistency >= 8:
                                st.caption("🟢 Highly consistent")
                            elif consistency >= 6:
                                st.caption("🟡 Moderately consistent")
                            else:
                                st.caption("🔴 Inconsistent patterns")

                        with col_m3:
                            uniformity = metrics['frequency_uniformity']
                            st.metric("Distribution", f"{uniformity:.2f}")
                            if uniformity < 2.0:
                                st.caption("🟢 Natural spread")
                            elif uniformity < 3.5:
                                st.caption("🟡 Slightly irregular")
                            else:
                                st.caption("🔴 Unusual patterns")

                        # Findings
                        st.markdown("---")
                        st.subheader("🔍 Detailed Findings")
                        for finding in result['findings']:
                            if "✓" in finding:
                                st.success(finding)
                            else:
                                st.warning(finding)

                        # Warnings
                        if result.get('warnings'):
                            st.markdown("---")
                            st.subheader("⚠️ Potential Issues Detected")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")

                        # Human-readable interpretation
                        st.markdown("---")
                        st.subheader("💡 What This Means")
                        st.markdown(result['interpretation'])

                        # Technical details (collapsible)
                        with st.expander("🔬 Technical Details (Advanced)"):
                            st.json(result['technical_details'])

                    else:
                        st.error(
                            f"❌ Analysis failed: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ FFT Analysis Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

        # DCT Analysis Section
        st.markdown("---")
        st.markdown("---")
        st.markdown("### 🧩 DCT (Discrete Cosine Transform) Anomaly Detection")
        st.write(
            "Analyzes JPEG compression patterns. Since most photos are saved as JPEG, "
            "editing leaves telltale signs in how the image is compressed."
        )

        if st.button("🚀 Detect DCT Anomalies", type="primary", key="dct_btn"):
            with st.spinner("Analyzing DCT coefficients..."):
                try:
                    result = frequency_analysis.detect_dct_anomalies(file_path)

                    if result.get('status') == 'success':
                        # Overall verdict
                        st.markdown("---")
                        st.subheader("🎯 Overall Assessment")

                        col_verdict1, col_verdict2, col_verdict3 = st.columns(
                            3)

                        with col_verdict1:
                            score = result['authenticity_score']
                            if score >= 80:
                                color = "🟢"
                            elif score >= 60:
                                color = "🟡"
                            else:
                                color = "🔴"
                            st.metric("Authenticity Score",
                                      f"{color} {score}/100")

                        with col_verdict2:
                            risk = result['risk_level']
                            risk_color = "🟢" if risk == "Low" else (
                                "🟡" if risk == "Medium" else "🔴")
                            st.metric("Risk Level", f"{risk_color} {risk}")

                        with col_verdict3:
                            anomaly_count = len(result.get('anomalies', []))
                            anomaly_color = "🟢" if anomaly_count == 0 else (
                                "🟡" if anomaly_count <= 2 else "🔴")
                            st.metric("Anomalies Found",
                                      f"{anomaly_color} {anomaly_count}")

                        st.info(f"**Verdict:** {result['verdict']}")

                        # Display DCT visualization
                        if result.get('dct_anomaly_map_path'):
                            st.markdown("---")
                            st.subheader("📊 DCT Analysis Visualization")
                            st.image(result['dct_anomaly_map_path'],
                                     caption="DCT Coefficient & Block Consistency Analysis",
                                     width='stretch')
                            st.caption(
                                "💡 **Left:** DCT coefficients (smooth areas top-left, details bottom-right) | **Right:** Block consistency (green = consistent, red = inconsistent)")

                        # User-friendly metrics
                        st.markdown("---")
                        st.subheader("📈 Content Breakdown")

                        metrics = result['metrics']
                        col_m1, col_m2, col_m3 = st.columns(3)

                        with col_m1:
                            smooth_pct = metrics['smooth_content_percentage']
                            st.metric("Smooth Areas", f"{smooth_pct:.1f}%")
                            if 40 < smooth_pct < 70:
                                st.caption("🟢 Natural balance")
                            elif smooth_pct > 80:
                                st.caption("🟡 Very smooth")
                            else:
                                st.caption("🟡 Low smoothness")

                        with col_m2:
                            detail_pct = metrics['detail_content_percentage']
                            st.metric("Textures & Details",
                                      f"{detail_pct:.1f}%")
                            st.caption("🔵 Natural textures")

                        with col_m3:
                            noise_pct = metrics['noise_edge_percentage']
                            st.metric("Edges & Noise", f"{noise_pct:.1f}%")
                            if noise_pct < 5:
                                st.caption("🟢 Normal levels")
                            elif noise_pct < 10:
                                st.caption("🟡 Elevated")
                            else:
                                st.caption("🔴 Very high")

                        # Compression quality indicators
                        st.markdown("---")
                        st.subheader("🎯 Compression Quality Indicators")

                        col_q1, col_q2 = st.columns(2)

                        with col_q1:
                            block_score = metrics['block_consistency_score']
                            st.metric("Block Consistency",
                                      f"{block_score:.1f}/10")
                            if block_score >= 8:
                                st.caption("🟢 Highly consistent")
                            elif block_score >= 5:
                                st.caption("🟡 Some variations")
                            else:
                                st.caption("🔴 Inconsistent blocks")

                        with col_q2:
                            comp_quality = metrics['compression_quality_indicator']
                            st.metric("Compression Quality",
                                      f"{comp_quality:.1f}/10")
                            if comp_quality >= 7:
                                st.caption("🟢 Clean compression")
                            elif comp_quality >= 4:
                                st.caption("🟡 Some artifacts")
                            else:
                                st.caption("🔴 Heavy compression")

                        # Findings
                        st.markdown("---")
                        st.subheader("🔍 Detailed Findings")
                        for finding in result['findings']:
                            if "✓" in finding:
                                st.success(finding)
                            else:
                                st.warning(finding)

                        # Specific anomalies
                        if result.get('anomalies'):
                            st.markdown("---")
                            st.subheader("🚨 Specific Anomalies Detected")
                            for anomaly in result['anomalies']:
                                st.error(f"🔴 {anomaly}")

                        # Warnings
                        if result.get('warnings'):
                            st.markdown("---")
                            st.subheader("⚠️ Warnings & Explanations")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")
                        else:
                            st.success(
                                "✅ No significant compression anomalies detected")

                        # Human-readable interpretation
                        st.markdown("---")
                        st.subheader("💡 What This Means")
                        st.markdown(result['interpretation'])

                        # Technical details (collapsible)
                        with st.expander("🔬 Technical Details (Advanced)"):
                            st.json(result['technical_details'])

                    else:
                        st.error(
                            f"❌ Analysis failed: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ DCT Analysis Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)
                    st.error(f"❌ DCT Analysis Error: {str(e)}")

    # --- TAB 9: DEEPFAKE DETECTION ---
    with tab9:
        st.subheader(" Deepfake & GAN Detection")
        st.write(
            "Detect AI-generated and deepfake images using spectral analysis and GAN fingerprint detection. "
            "GANs leave characteristic frequency-domain patterns that can be detected."
        )

        # GAN Artifacts Section
        st.markdown("---")
        st.markdown("### 🎭 General Deepfake Artifact Detection")
        st.write("Analyze for common deepfake indicators and manipulation artifacts")

        if st.button("🚀 Detect Deepfake Artifacts", type="primary", key="artifacts_btn"):
            with st.spinner("Analyzing for deepfake artifacts..."):
                try:
                    result = deepfake_detector.detect_deepfake_artifacts(
                        file_path)

                    if result.get('status') == 'success':
                        # Display metrics
                        st.markdown("---")
                        st.subheader("📊 Artifact Analysis")

                        if result.get('metrics'):
                            metrics = result['metrics']
                            col_a1, col_a2, col_a3 = st.columns(3)

                            with col_a1:
                                if 'face_consistency' in metrics:
                                    st.metric(
                                        "Face Consistency", f"{metrics['face_consistency']:.2f}")

                            with col_a2:
                                if 'edge_sharpness' in metrics:
                                    st.metric("Edge Sharpness",
                                              f"{metrics['edge_sharpness']:.2f}")

                            with col_a3:
                                if 'color_anomalies' in metrics:
                                    st.metric("Color Anomalies",
                                              metrics['color_anomalies'])

                        # Warnings
                        if result.get('warnings'):
                            st.markdown("---")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")

                        # Interpretation
                        if result.get('interpretation'):
                            st.info(f"💡 {result['interpretation']}")

                    else:
                        st.json(result)

                except Exception as e:
                    st.error(f"❌ Artifact Detection Error: {str(e)}")

        # GAN Fingerprint Section
        st.markdown("---")
        st.markdown("---")
        st.markdown("### 🧠 GAN Fingerprint Detection")
        st.write(
            "Advanced spectral analysis to detect GAN-specific frequency signatures")

        if st.button("🚀 Detect GAN Fingerprint", type="primary", key="gan_btn"):
            with st.spinner("Analyzing GAN fingerprint patterns..."):
                try:
                    result = deepfake_detector.detect_gan_fingerprint(
                        file_path)

                    if result.get('status') == 'success':
                        # GAN Score Display
                        st.markdown("---")
                        st.subheader("🎯 GAN Detection Score")

                        col_score1, col_score2, col_score3 = st.columns(3)

                        with col_score1:
                            gan_score = result['metrics'].get('gan_score', 0)

                            # Color-coded based on score
                            if gan_score > 0.7:
                                color = "🔴"
                                assessment = "HIGH RISK"
                            elif gan_score > 0.4:
                                color = "🟡"
                                assessment = "MEDIUM RISK"
                            else:
                                color = "🟢"
                                assessment = "LOW RISK"

                            st.metric("GAN Score", f"{color} {gan_score:.3f}")
                            st.caption(assessment)

                        with col_score2:
                            likelihood = result.get(
                                'gan_likelihood', 'Unknown')
                            st.metric("GAN Likelihood", likelihood)

                        with col_score3:
                            indicators = result.get('gan_indicators', [])
                            st.metric("Indicators Detected", len(indicators))

                        # Detailed Metrics
                        st.markdown("---")
                        st.subheader("📈 Spectral Analysis Metrics")

                        metrics = result['metrics']
                        col_m1, col_m2, col_m3 = st.columns(3)

                        with col_m1:
                            if 'radial_frequency_variance' in metrics:
                                st.metric(
                                    "Radial Frequency Variance", f"{metrics['radial_frequency_variance']:.2f}")

                        with col_m2:
                            if 'spectral_peaks_detected' in metrics:
                                st.metric("Spectral Peaks",
                                          metrics['spectral_peaks_detected'])

                        with col_m3:
                            if 'quadrant_symmetry' in metrics:
                                st.metric("Quadrant Symmetry",
                                          f"{metrics['quadrant_symmetry']:.4f}")

                        # Radial Profile Visualization
                        if result.get('radial_profile'):
                            st.markdown("---")
                            st.subheader("🌊 Radial Frequency Profile")

                            import matplotlib.pyplot as plt
                            import numpy as np

                            fig, ax = plt.subplots(figsize=(10, 4))
                            profile = result['radial_profile']
                            ax.plot(profile, linewidth=2, color='#1f77b4')
                            ax.set_xlabel(
                                'Radial Distance from Center', fontsize=11)
                            ax.set_ylabel('Average Magnitude', fontsize=11)
                            ax.set_title('Radial Frequency Distribution',
                                         fontsize=13, fontweight='bold')
                            ax.grid(alpha=0.3, linestyle='--')
                            plt.tight_layout()
                            st.pyplot(fig)
                            plt.close()

                            st.caption(
                                "💡 GANs produce characteristic periodic patterns in radial frequency distribution")

                        # GAN Indicators
                        if result.get('gan_indicators'):
                            st.markdown("---")
                            st.subheader("🚩 GAN Indicators Detected")
                            for indicator in result['gan_indicators']:
                                st.warning(f"⚠️ {indicator}")
                        else:
                            st.success("✅ No strong GAN indicators detected")

                        # Interpretation
                        if result.get('interpretation'):
                            st.markdown("---")
                            st.info(f"💡 {result['interpretation']}")

                        # Raw data
                        with st.expander("📋 View Raw Analysis Data"):
                            st.json(result)

                    else:
                        st.error(
                            f"❌ Analysis Error: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ GAN Detection Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

    # --- TAB 10: RESAMPLING DETECTION ---
    with tab10:
        st.subheader("🔀 Resampling & Interpolation Detection")
        st.write(
            "Detect image resizing and resampling artifacts that indicate manipulation. "
            "Resampling leaves periodic patterns that can be detected through frequency analysis."
        )

        # Resampling Detection Section
        st.markdown("---")
        st.markdown("### 🔍 Resampling Detection")
        st.write("Analyze for periodic patterns indicating image has been resized")

        if st.button("🚀 Detect Resampling", type="primary", key="resample_btn"):
            with st.spinner("Analyzing for resampling artifacts..."):
                try:
                    result = resampling_detector.detect_resampling(file_path)

                    if result.get('status') == 'success':
                        # Resampling Detection Result
                        st.markdown("---")
                        st.subheader("🎯 Detection Result")

                        col_r1, col_r2, col_r3 = st.columns(3)

                        with col_r1:
                            detected = result.get('resampled', False)
                            indicator = "🔴" if detected else "🟢"
                            status = "DETECTED" if detected else "NOT DETECTED"
                            st.metric("Resampling", f"{indicator} {status}")

                        with col_r2:
                            if 'confidence' in result:
                                confidence = result['confidence']
                                st.metric("Confidence", f"{confidence:.2%}")

                        with col_r3:
                            if 'periodicity_score' in result.get('metrics', {}):
                                score = result['metrics']['periodicity_score']
                                st.metric("Periodicity Score", f"{score:.3f}")

                        # Detailed Metrics
                        if result.get('metrics'):
                            st.markdown("---")
                            st.subheader("📊 Analysis Metrics")

                            metrics = result['metrics']
                            col_m1, col_m2 = st.columns(2)

                            with col_m1:
                                if 'peak_count' in metrics:
                                    st.metric("Detected Peaks",
                                              metrics['peak_count'])
                                if 'variance_ratio' in metrics:
                                    st.metric("Variance Ratio",
                                              f"{metrics['variance_ratio']:.3f}")

                            with col_m2:
                                if 'estimated_scale_factor' in metrics:
                                    st.metric(
                                        "Est. Scale Factor", f"{metrics['estimated_scale_factor']:.2f}")
                                if 'direction' in metrics:
                                    st.metric(
                                        "Direction", metrics['direction'])

                        # Visualization if available
                        if result.get('periodicity_map_path'):
                            st.markdown("---")
                            st.subheader("🖼️ Periodicity Map")
                            st.image(result['periodicity_map_path'],
                                     caption="Resampling Artifact Visualization",
                                     width='stretch')

                        # Warnings
                        if result.get('warnings'):
                            st.markdown("---")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")
                        else:
                            st.success("✅ No resampling artifacts detected")

                        # Interpretation
                        if result.get('interpretation'):
                            st.info(f"💡 {result['interpretation']}")

                    else:
                        st.json(result)

                except Exception as e:
                    st.error(f"❌ Resampling Detection Error: {str(e)}")

        # Interpolation Method Detection
        st.markdown("---")
        st.markdown("---")
        st.markdown("### 🧩 Interpolation Method Identification")
        st.write("Identify the interpolation algorithm used during resampling")

        if st.button("🚀 Identify Interpolation Method", type="primary", key="interp_btn"):
            with st.spinner("Analyzing interpolation patterns..."):
                try:
                    result = resampling_detector.detect_interpolation_method(
                        file_path)

                    if result.get('status') == 'success':
                        # Method Identification
                        st.markdown("---")
                        st.subheader("🎯 Identified Method")

                        col_i1, col_i2 = st.columns(2)

                        with col_i1:
                            method = result.get('method', 'Unknown')
                            st.metric("Interpolation Method", method)

                        with col_i2:
                            if 'confidence' in result:
                                confidence = result['confidence']
                                color = "🟢" if confidence > 0.7 else (
                                    "🟡" if confidence > 0.4 else "🔴")
                                st.metric("Confidence",
                                          f"{color} {confidence:.2%}")

                        # Classification scores
                        if result.get('method_scores'):
                            st.markdown("---")
                            st.subheader("📈 Method Classification Scores")

                            import pandas as pd
                            scores_df = pd.DataFrame([
                                {"Method": method, "Score": f"{score:.4f}"}
                                for method, score in result['method_scores'].items()
                            ]).sort_values(by="Score", ascending=False)

                            # Characteristics
                            st.dataframe(scores_df, width='stretch')
                        if result.get('characteristics'):
                            st.markdown("---")
                            st.subheader("🔍 Detected Characteristics")
                            for char in result['characteristics']:
                                st.info(f"• {char}")

                        # Warnings
                        if result.get('warnings'):
                            st.markdown("---")
                            for warning in result['warnings']:
                                st.warning(f"⚠️ {warning}")

                        # Interpretation
                        if result.get('interpretation'):
                            st.markdown("---")
                            st.info(f"💡 {result['interpretation']}")

                    else:
                        st.json(result)

                except Exception as e:
                    st.error(f"❌ Interpolation Detection Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

    # --- TAB 11: STEGANOGRAPHY DETECTION ---
    with tab11:
        st.subheader("🔐 LSB Steganography Detection")
        st.write(
            "Detect hidden data in images using statistical analysis of Least Significant Bits (LSB). "
            "This module uses chi-square testing to identify non-natural bit patterns that may indicate steganography."
        )

        if st.button("🚀 Detect Hidden Data", type="primary"):
            with st.spinner("Analyzing LSB patterns and performing chi-square tests..."):
                try:
                    # Perform steganography detection
                    probability, visual_map, details = steganography_detection.detect_lsb_steganography(
                        file_path
                    )

                    # Check for errors
                    if 'error' in details:
                        st.error(f"❌ Analysis Error: {details['error']}")
                    else:
                        # ========== SUMMARY CARD ==========
                        st.markdown("---")
                        st.subheader("📊 Detection Summary")

                        col1, col2, col3 = st.columns(3)

                        interpretation = details['interpretation']

                        with col1:
                            color_emoji = interpretation['color']
                            st.metric("Overall Probability", 
                                     f"{probability:.1f}%")
                            st.markdown(f"### {color_emoji} **{interpretation['risk_level']} Risk**")

                        with col2:
                            st.metric("Confidence", interpretation['confidence'])
                            st.metric("Risk Level", interpretation['risk_level'])

                        with col3:
                            st.metric("Image Size", 
                                     f"{details['image_info']['width']}×{details['image_info']['height']}")
                            st.metric("Total Pixels", 
                                     f"{details['image_info']['total_pixels']:,}")

                        # Description
                        st.info(f"**Interpretation**: {interpretation['description']}")

                        # ========== VISUAL ANALYSIS MAP ==========
                        st.markdown("---")
                        st.subheader("🔥 Visual Analysis Heatmap")
                        st.write(
                            "Heatmap shows steganography probability for each image region. "
                            "Hot colors (red/orange) indicate high suspicion, cool colors (blue) indicate normal patterns."
                        )
                        
                        if visual_map is not None:
                            st.image(visual_map, caption="LSB Analysis Heatmap", 
                                   use_container_width=True)

                        # ========== CHANNEL RESULTS ==========
                        st.markdown("---")
                        st.subheader("📺 Per-Channel Analysis")
                        
                        channel_cols = st.columns(3)
                        
                        for idx, (channel, channel_data) in enumerate(details['channel_results'].items()):
                            with channel_cols[idx]:
                                st.markdown(f"**{channel.upper()} Channel**")
                                
                                # Create metrics
                                prob_val = channel_data['steganography_probability']
                                
                                if prob_val < 20:
                                    risk = "🟢 Low"
                                elif prob_val < 50:
                                    risk = "🟡 Medium"
                                elif prob_val < 80:
                                    risk = "🟠 High"
                                else:
                                    risk = "🔴 Critical"
                                
                                st.metric("Probability", f"{prob_val:.1f}%")
                                st.metric("Risk", risk)
                                
                                # Show LSB distribution
                                dist = channel_data['lsb_distribution']
                                st.caption(f"LSB Distribution: {dist['zeros']} zeros, {dist['ones']} ones")
                                
                                # Show chi-square stats
                                with st.expander("Statistical Details"):
                                    st.json({
                                        "Chi-Square Statistic": f"{channel_data['chi_square_statistic']:.4f}",
                                        "P-Value": f"{channel_data['p_value']:.6f}",
                                        "Zeros": dist['zeros'],
                                        "Ones": dist['ones']
                                    })

                        # ========== INTERPRETATION GUIDE ==========
                        st.markdown("---")
                        st.subheader("📖 How to Interpret Results")
                        
                        st.markdown("""
                        **Understanding the Probability Score:**
                        - **0-20%**: LSB distribution appears natural. No strong evidence of steganography.
                        - **20-50%**: Some statistical anomalies detected. Further investigation recommended.
                        - **50-80%**: Significant LSB anomalies. Strong indication of hidden data.
                        - **80-100%**: Severe anomalies. Very high likelihood of steganography.
                        
                        **What to Look For:**
                        - **Hot regions** in the heatmap (red/orange areas) indicate suspicious LSB patterns
                        - **Uneven bit distribution** (far from 50/50) suggests non-natural data
                        - **High chi-square statistic** with low p-value indicates statistical significance
                        - **Consistent anomalies** across multiple channels strengthen suspicion
                        
                        **Important Notes:**
                        - This test detects LSB steganography, not all types of hidden data
                        - High scores don't always mean malicious intent (watermarks, metadata)
                        - Some cameras naturally produce non-random LSB patterns
                        - Use alongside other forensic techniques for comprehensive analysis
                        """)

                except Exception as e:
                    st.error(f"❌ Steganography Detection Error: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)

    # --- TAB 12: HASH VERIFICATION ---
    with tab12:
        st.subheader("🔑 Cryptographic Hash Verification & Provenance Tracking")
        st.write(
            "Verify image authenticity using perceptual and cryptographic hashing. "
            "Track image provenance with blockchain-based storage and detect unauthorized modifications."
        )

        # Create two sub-sections
        action = st.radio(
            "Select Action:",
            ["Verify Image Provenance", "Add to Blockchain Database", "Database Management"],
            horizontal=True
        )

        if action == "Verify Image Provenance":
            st.markdown("### 🔍 Verify Image Against Database")
            st.caption("Check if this image exists in the database and assess its authenticity")
            
            if st.button("🚀 Verify Image", type="primary"):
                with st.spinner("Generating hashes and searching database..."):
                    try:
                        # Verify provenance
                        score, history, validity, details = hash_verification.verify_image_provenance(
                            file_path
                        )

                        if 'error' in details:
                            st.error(f"❌ Verification Error: {details['error']}")
                        else:
                            # ========== AUTHENTICITY SUMMARY ==========
                            st.markdown("---")
                            st.subheader("📊 Authenticity Assessment")

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                # Color based on score
                                if score >= 85:
                                    color = "🟢"
                                    verdict = "Authenticated"
                                elif score >= 70:
                                    color = "🟡"
                                    verdict = "Likely Authentic"
                                elif score >= 55:
                                    color = "🟠"
                                    verdict = "Questionable"
                                else:
                                    color = "🔴"
                                    verdict = "Unknown/Modified"
                                
                                st.metric("Authenticity Score", f"{score}/100")
                                st.markdown(f"### {color} **{verdict}**")

                            with col2:
                                st.metric("Matches Found", details['matches_found'])
                                chain_status = validity.get('chain_of_custody', 'Unknown')
                                st.metric("Chain of Custody", chain_status)

                            with col3:
                                if validity.get('valid'):
                                    st.metric("Legal Status", "✅ Admissible")
                                else:
                                    st.metric("Legal Status", "❌ Not Admissible")
                                
                                confidence = validity.get('confidence', 'Unknown')
                                st.metric("Confidence", confidence)

                            # ========== LEGAL VALIDITY ==========
                            st.markdown("---")
                            st.subheader("⚖️ Legal Validity Assessment")
                            
                            valid = validity.get('valid')
                            if valid is True:
                                st.success(f"✅ **Valid**: {validity['reason']}")
                            elif valid is False:
                                st.error(f"❌ **Invalid**: {validity['reason']}")
                            else:
                                st.warning(f"⚠️ **Uncertain**: {validity['reason']}")
                            
                            if 'modifications' in validity:
                                st.info(f"📝 **Modifications Detected**: {validity['modifications']}")

                            # ========== HASH INFORMATION ==========
                            st.markdown("---")
                            st.subheader("🔐 Hash Information")
                            
                            col_hash1, col_hash2 = st.columns(2)
                            
                            with col_hash1:
                                st.markdown("**Cryptographic Hash (SHA-256)**")
                                st.code(details['current_hashes']['sha256'], language=None)
                                st.caption("Exact file fingerprint - any modification changes this completely")

                            with col_hash2:
                                st.markdown("**Perceptual Hash (pHash)**")
                                st.code(details['current_hashes']['perceptual']['phash'], language=None)
                                st.caption("Similarity-based hash - resistant to minor modifications")

                            # Show all perceptual hashes in expander
                            with st.expander("🔍 View All Perceptual Hashes"):
                                st.json(details['current_hashes']['perceptual'])

                            # ========== MODIFICATION HISTORY ==========
                            if history:
                                st.markdown("---")
                                st.subheader("📜 Modification History")
                                st.write(f"Found {len(history)} related records in database:")
                                
                                import pandas as pd
                                history_df = pd.DataFrame(history)
                                st.dataframe(history_df, use_container_width=True)

                            # ========== MATCH DETAILS ==========
                            if details['match_details']:
                                st.markdown("---")
                                st.subheader("🎯 Top Matches")
                                
                                for idx, match in enumerate(details['match_details'][:3], 1):
                                    with st.expander(f"Match #{idx}: {match['record']['filename']} ({match['similarity']:.1f}% similar)"):
                                        col_m1, col_m2 = st.columns(2)
                                        
                                        with col_m1:
                                            st.json({
                                                "Match Type": match['match_type'].upper(),
                                                "Similarity": f"{match['similarity']:.2f}%",
                                                "Hash Distance": match['hash_distance'],
                                                "Timestamp": match['record']['timestamp']
                                            })
                                        
                                        with col_m2:
                                            st.json({
                                                "Filename": match['record']['filename'],
                                                "File Size": f"{match['record']['file_size']:,} bytes",
                                                "SHA-256": match['record']['sha256'][:16] + "..."
                                            })

                            # ========== INTERPRETATION GUIDE ==========
                            st.markdown("---")
                            st.subheader("📖 Interpretation Guide")
                            st.markdown("""
                            **Authenticity Scores:**
                            - **100**: Exact cryptographic match - identical file
                            - **85-99**: Strong perceptual match - minor modifications only
                            - **70-84**: Moderate match - some modifications detected
                            - **55-69**: Weak match - significant changes
                            - **0-54**: No match or unknown provenance
                            
                            **Chain of Custody:**
                            - **Intact**: Image matches database with exact hash
                            - **Likely Intact**: Minor modifications (compression, resize)
                            - **Questionable**: Moderate modifications detected
                            - **Broken**: Significant changes or no database record
                            
                            **Legal Admissibility:**
                            - Requires intact chain of custody
                            - Exact hash match provides strongest evidence
                            - Modifications must be documented and explained
                            - Database integrity must be maintained
                            """)

                    except Exception as e:
                        st.error(f"❌ Hash Verification Error: {str(e)}")
                        with st.expander("🐛 View Error Details"):
                            st.exception(e)

        elif action == "Add to Blockchain Database":
            st.markdown("### 📥 Register Image in Database")
            st.caption("Add this image to the blockchain database for future verification")
            
            if st.button("➕ Add to Database", type="primary"):
                with st.spinner("Generating hashes and adding to blockchain..."):
                    try:
                        record = hash_verification.add_to_blockchain(file_path)
                        
                        st.success("✅ Image successfully added to blockchain database!")
                        
                        st.markdown("---")
                        st.subheader("📋 Record Details")
                        
                        col_r1, col_r2, col_r3 = st.columns(3)
                        
                        with col_r1:
                            st.metric("Record ID", record['id'])
                            st.metric("Filename", record['filename'])
                        
                        with col_r2:
                            st.metric("File Size", f"{record['file_size']:,} bytes")
                            st.metric("Format", record['image_info'].get('format', 'Unknown'))
                        
                        with col_r3:
                            img_info = record['image_info']
                            st.metric("Dimensions", 
                                     f"{img_info.get('width', '?')}×{img_info.get('height', '?')}")
                            st.metric("Timestamp", record['timestamp'][:19])
                        
                        # Show hashes
                        st.markdown("---")
                        st.subheader("🔐 Generated Hashes")
                        
                        with st.expander("View Cryptographic Hash"):
                            st.code(record['sha256'], language=None)
                        
                        with st.expander("View Perceptual Hashes"):
                            st.json(record['perceptual_hashes'])

                    except Exception as e:
                        st.error(f"❌ Database Addition Error: {str(e)}")
                        with st.expander("🐛 View Error Details"):
                            st.exception(e)

        else:  # Database Management
            st.markdown("### 🗄️ Database Management")
            
            # Get database stats
            try:
                stats = hash_verification.get_database_stats()
                
                st.markdown("#### 📊 Database Statistics")
                col_s1, col_s2, col_s3 = st.columns(3)
                
                with col_s1:
                    st.metric("Total Records", stats['total_records'])
                
                with col_s2:
                    st.metric("Database Created", 
                             stats.get('created', 'Unknown')[:10] if stats.get('created') else 'Unknown')
                
                with col_s3:
                    st.metric("Last Updated", 
                             stats.get('last_updated', 'Never')[:10] if stats.get('last_updated') != 'Never' else 'Never')
                
                if stats['total_records'] > 0:
                    st.markdown("---")
                    col_d1, col_d2 = st.columns(2)
                    
                    with col_d1:
                        st.metric("Oldest Record", stats.get('oldest_record', 'N/A')[:19])
                    
                    with col_d2:
                        st.metric("Newest Record", stats.get('newest_record', 'N/A')[:19])
                
                # Export/Import
                st.markdown("---")
                st.markdown("#### 📤 Export/Import Database")
                
                col_ei1, col_ei2 = st.columns(2)
                
                with col_ei1:
                    if st.button("📤 Export Database"):
                        try:
                            export_path = hash_verification.export_database()
                            st.success(f"✅ Database exported to: {export_path}")
                            
                            # Offer download
                            if os.path.exists(export_path):
                                with open(export_path, 'r') as f:
                                    st.download_button(
                                        label="⬇️ Download Export",
                                        data=f.read(),
                                        file_name=os.path.basename(export_path),
                                        mime="application/json"
                                    )
                        except Exception as e:
                            st.error(f"Export failed: {str(e)}")
                
                with col_ei2:
                    st.caption("Import functionality requires file upload")
                    st.info("Upload a previously exported database JSON file to import records")

            except Exception as e:
                st.error(f"❌ Database Error: {str(e)}")

    # --- TAB 13: INFO ---
    with tab13:
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
        - **Steganography Detection**: LSB statistical analysis for hidden data
        - **Hash Verification**: Cryptographic provenance tracking and authentication
        """)

    # --- TAB 14: ADVANCED ---
    with tab14:
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
