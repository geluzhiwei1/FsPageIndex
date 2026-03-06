"""
MediaProcessor - Enhanced image and video processing with AI support
Supports VLM (Vision Language Model) and OCR APIs
"""
import os
import asyncio
import base64
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import logging

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class ImageProcessor:
    """Enhanced image processor with VLM and OCR support"""

    def __init__(
        self,
        vlm_api_key: Optional[str] = None,
        vlm_model: str = "gpt-4o",  # GPT-4o has vision capabilities
        ocr_api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize image processor

        Args:
            vlm_api_key: Vision Language Model API key (OpenAI)
            vlm_model: VLM model name (default: gpt-4o)
            ocr_api_key: OCR API key (OpenAI)
            logger: Optional logger instance
        """
        self.vlm_api_key = vlm_api_key or os.getenv('OPENAI_API_KEY')
        self.vlm_model = vlm_model
        self.ocr_api_key = ocr_api_key or os.getenv('OPENAI_API_KEY')
        self.logger = logger or logging.getLogger('ImageProcessor')

        # Check API availability
        self.vlm_enabled = bool(self.vlm_api_key)
        self.ocr_enabled = bool(self.ocr_api_key)

        if self.vlm_enabled:
            self.logger.info(f"VLM analysis enabled: {vlm_model}")
        if self.ocr_enabled:
            self.logger.info("OCR analysis enabled")

    async def process_image(
        self,
        file_path: str,
        use_vlm: bool = True,
        use_ocr: bool = True,
        use_exif: bool = True
    ) -> dict:
        """
        Process image file with enhanced capabilities

        Args:
            file_path: Path to image file
            use_vlm: Use VLM to analyze image content
            use_ocr: Use OCR to extract text from image
            use_exif: Extract EXIF metadata

        Returns:
            Enhanced tree structure with image content
        """
        self.logger.info(f"Processing image: {file_path}")

        nodes = []
        node_counter = 0

        # 1. Basic image information
        if PIL_AVAILABLE and use_exif:
            basic_info = await self._extract_basic_info(file_path)
            node_counter += 1

            if basic_info:
                nodes.append({
                    'node_id': str(node_counter).zfill(4),
                    'title': f"Image Info: {basic_info.get('format', 'Unknown')}",
                    'type': 'image_info',
                    'summary': self._format_image_summary(basic_info),
                    'metadata': basic_info
                })

        # 2. EXIF metadata
        if PIL_AVAILABLE and use_exif:
            exif_info = await self._extract_exif(file_path)
            if exif_info:
                node_counter += 1
                nodes.append({
                    'node_id': str(node_counter).zfill(4),
                    'title': "EXIF Metadata",
                    'type': 'exif_metadata',
                    'summary': self._format_exif_summary(exif_info),
                    'metadata': exif_info
                })

        # 3. VLM Content Analysis
        if use_vlm and self.vlm_enabled:
            vlm_result = await self._analyze_with_vlm(file_path)
            if vlm_result:
                node_counter += 1
                nodes.append({
                    'node_id': str(node_counter).zfill(4),
                    'title': "AI Content Analysis",
                    'type': 'ai_analysis',
                    'summary': vlm_result['description'],
                    'metadata': {
                        'model': self.vlm_model,
                        'analysis_time': vlm_result.get('analysis_time'),
                        'confidence': vlm_result.get('confidence', 'high')
                    }
                })

        # 4. OCR Text Extraction
        if use_ocr and self.ocr_enabled:
            ocr_result = await self._extract_text_with_ocr(file_path)
            if ocr_result and ocr_result.get('text'):
                node_counter += 1
                nodes.append({
                    'node_id': str(node_counter).zfill(4),
                    'title': "Extracted Text",
                    'type': 'ocr_text',
                    'summary': f"Text found in image: {len(ocr_result['text'])} characters",
                    'text': ocr_result['text'],
                    'metadata': {
                        'language': ocr_result.get('language', 'unknown'),
                        'confidence': ocr_result.get('confidence', 0)
                    }
                })

        # Build tree structure
        tree = {
            'title': os.path.basename(file_path),
            'file_type': 'image',
            'format': self._get_image_format(file_path),
            'nodes': nodes,
            'has_content_analysis': len(nodes) > 0,
            'analysis_types': [node['type'] for node in nodes]
        }

        return tree

    async def _extract_basic_info(self, file_path: str) -> Optional[dict]:
        """Extract basic image information"""
        if not PIL_AVAILABLE:
            return None

        try:
            with Image.open(file_path) as img:
                return {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,  # (width, height)
                    'width': img.width,
                    'height': img.height,
                    'bits': img.bits if hasattr(img, 'bits') else None
                }
        except Exception as e:
            self.logger.warning(f"Failed to extract basic info: {e}")
            return None

    async def _extract_exif(self, file_path: str) -> Optional[dict]:
        """Extract EXIF metadata from image"""
        if not PIL_AVAILABLE:
            return None

        try:
            with Image.open(file_path) as img:
                if not hasattr(img, '_getexif'):
                    return None

                exif = img._getexif()
                if not exif:
                    return None

                exif_data = {}
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = value

                return exif_data
        except Exception as e:
            self.logger.warning(f"Failed to extract EXIF: {e}")
            return None

    async def _analyze_with_vlm(self, file_path: str) -> Optional[dict]:
        """Analyze image content using Vision Language Model"""
        if not self.vlm_enabled:
            return None

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.vlm_api_key)

            # Encode image to base64
            with open(file_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
                image_type = self._get_mime_type(file_path)

            start_time = datetime.now()

            # Call GPT-4o with vision
            response = await client.chat.completions.create(
                model=self.vlm_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this image and provide a detailed description including:
1. Main subjects and objects
2. Setting or location
3. Colors and mood
4. Text visible in the image
5. Notable features or details
6. Overall context or scene description

Be specific and concise (max 200 words)."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.3
            )

            analysis_time = (datetime.now() - start_time).total_seconds()

            description = response.choices[0].message.content.strip()

            self.logger.info(f"VLM analysis completed in {analysis_time:.2f}s")

            return {
                'description': description,
                'analysis_time': analysis_time,
                'model': self.vlm_model
            }

        except Exception as e:
            self.logger.error(f"VLM analysis failed: {e}")
            return None

    async def _extract_text_with_ocr(self, file_path: str) -> Optional[dict]:
        """Extract text from image using OCR"""
        if not self.ocr_enabled:
            return None

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.ocr_api_key)

            # Encode image to base64
            with open(file_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
                image_type = self._get_mime_type(file_path)

            # Use GPT-4o for OCR (it has vision capabilities)
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Extract all text visible in this image.
Return ONLY the extracted text, nothing else.
If there is no text, return an empty string."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0
            )

            extracted_text = response.choices[0].message.content.strip()

            # Remove quotes if the model added them
            if extracted_text.startswith('"') and extracted_text.endswith('"'):
                extracted_text = extracted_text[1:-1]

            if not extracted_text or extracted_text.lower() in ['no text', 'none', '']:
                return None

            self.logger.info(f"OCR extracted {len(extracted_text)} characters")

            return {
                'text': extracted_text,
                'language': 'unknown',  # Could add language detection
                'confidence': 0.9  # GPT-4o is quite accurate
            }

        except Exception as e:
            self.logger.error(f"OCR extraction failed: {e}")
            return None

    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type for image"""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        return mime_types.get(ext, 'image/jpeg')

    def _get_image_format(self, file_path: str) -> str:
        """Get image format"""
        ext = Path(file_path).suffix.lower()
        format_map = {
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG',
            '.png': 'PNG',
            '.gif': 'GIF',
            '.webp': 'WebP',
            '.bmp': 'BMP',
            '.svg': 'SVG'
        }
        return format_map.get(ext, 'Unknown')

    def _format_image_summary(self, basic_info: dict) -> str:
        """Format basic image info into summary"""
        width = basic_info.get('width', 0)
        height = basic_info.get('height', 0)
        format_type = basic_info.get('format', 'Unknown')
        mode = basic_info.get('mode', 'Unknown')

        return f"{format_type} image {width}x{height}, {mode} mode"

    def _format_exif_summary(self, exif_info: dict) -> str:
        """Format EXIF info into summary"""
        important_fields = []

        if 'DateTimeOriginal' in exif_info:
            important_fields.append(f"Date: {exif_info['DateTimeOriginal']}")
        if 'Make' in exif_info:
            important_fields.append(f"Camera: {exif_info['Make']} {exif_info.get('Model', '')}")
        if 'Flash' in exif_info:
            flash_status = "Fired" if exif_info['Flash'] else "Did not fire"
            important_fields.append(f"Flash: {flash_status}")
        if 'FNumber' in exif_info:
            important_fields.append(f"Aperture: f/{exif_info['FNumber']}")

        return ', '.join(important_fields) if important_fields else "EXIF data available"


class VideoProcessor:
    """Enhanced video processor with frame analysis and subtitle extraction"""

    def __init__(
        self,
        vlm_api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize video processor

        Args:
            vlm_api_key: Vision Language Model API key for frame analysis
            logger: Optional logger instance
        """
        self.vlm_api_key = vlm_api_key or os.getenv('OPENAI_API_KEY')
        self.logger = logger or logging.getLogger('VideoProcessor')

        self.vlm_enabled = bool(self.vlm_api_key)
        self.cv2_enabled = CV2_AVAILABLE

    async def process_video(
        self,
        file_path: str,
        analyze_frames: bool = True,
        num_frames: int = 3,
        use_vlm: bool = True
    ) -> dict:
        """
        Process video file with enhanced capabilities

        Args:
            file_path: Path to video file
            analyze_frames: Extract and analyze key frames
            num_frames: Number of frames to analyze
            use_vlm: Use VLM to analyze frame content

        Returns:
            Enhanced tree structure with video content
        """
        self.logger.info(f"Processing video: {file_path}")

        nodes = []
        node_counter = 0

        # 1. Basic video information
        if self.cv2_enabled:
            video_info = await self._extract_video_info(file_path)
            if video_info:
                node_counter += 1
                nodes.append({
                    'node_id': str(node_counter).zfill(4),
                    'title': f"Video Info: {video_info.get('codec', 'Unknown')}",
                    'type': 'video_info',
                    'summary': self._format_video_summary(video_info),
                    'metadata': video_info
                })

        # 2. Frame analysis
        if analyze_frames and self.cv2_enabled:
            frames_info = await self._extract_frames(file_path, num_frames)
            if frames_info:
                node_counter += 1
                nodes.append({
                    'node_id': str(node_counter).zfill(4),
                    'title': f"Key Frames ({len(frames_info['frames'])} frames)",
                    'type': 'video_frames',
                    'summary': f"Frames extracted at {frames_info['interval']}s intervals",
                    'metadata': frames_info
                })

        # 3. VLM Frame Analysis
        if use_vlm and self.vlm_enabled and analyze_frames:
            frame_analysis = await self._analyze_frames_with_vlm(file_path, num_frames)
            if frame_analysis:
                node_counter += 1
                nodes.append({
                    'node_id': str(node_counter).zfill(4),
                    'title': "AI Frame Analysis",
                    'type': 'ai_frame_analysis',
                    'summary': self._format_frame_analysis_summary(frame_analysis),
                    'metadata': frame_analysis
                })

        # Build tree structure
        tree = {
            'title': os.path.basename(file_path),
            'file_type': 'video',
            'format': self._get_video_format(file_path),
            'nodes': nodes,
            'has_content_analysis': len(nodes) > 0,
            'analysis_types': [node['type'] for node in nodes]
        }

        return tree

    async def _extract_video_info(self, file_path: str) -> Optional[dict]:
        """Extract basic video information"""
        if not self.cv2_enabled:
            return None

        try:
            cap = cv2.VideoCapture(file_path)

            if not cap.isOpened():
                return None

            info = {}

            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if fps > 0:
                duration = frame_count / fps
                info['duration'] = duration
                info['duration_formatted'] = self._format_duration(duration)

            info['fps'] = fps
            info['frame_count'] = frame_count
            info['width'] = width
            info['height'] = height
            info['resolution'] = f"{width}x{height}"

            cap.release()

            return info

        except Exception as e:
            self.logger.warning(f"Failed to extract video info: {e}")
            return None

    async def _extract_frames(self, file_path: str, num_frames: int) -> Optional[dict]:
        """Extract key frames from video"""
        if not self.cv2_enabled:
            return None

        try:
            cap = cv2.VideoCapture(file_path)

            if not cap.isOpened():
                return None

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if fps <= 0:
                cap.release()
                return None

            duration = frame_count / fps
            interval = duration / (num_frames + 1)

            frames = []
            for i in range(1, num_frames + 1):
                frame_time = i * interval
                frame_number = int(frame_time * fps)

                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()

                if ret:
                    # Save frame to temporary file
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                        cv2.imwrite(f.name, frame)
                        frames.append({
                            'frame_number': frame_number,
                            'timestamp': frame_time,
                            'temp_file': f.name
                        })

            cap.release()

            return {
                'frames': frames,
                'interval': interval,
                'total_frames': frame_count
            }

        except Exception as e:
            self.logger.warning(f"Failed to extract frames: {e}")
            return None

    async def _analyze_frames_with_vlm(self, file_path: str, num_frames: int) -> Optional[dict]:
        """Analyze video frames using VLM"""
        if not self.vlm_enabled:
            return None

        frames_info = await self._extract_frames(file_path, num_frames)
        if not frames_info:
            return None

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.vlm_api_key)

            analyses = []

            for frame_data in frames_info['frames']:
                # Read frame image
                if not os.path.exists(frame_data['temp_file']):
                    continue

                # Encode frame to base64
                with open(frame_data['temp_file'], 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode()

                # Analyze frame with VLM
                response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": """Describe this video frame in 50 words or less:
1. Main subject or action
2. Setting or background
3. Colors and lighting
4. Notable elements"""
                                },
                                {
                                    "type": "image_url",
                                    'image_url': {
                                        'url': f"data:image/jpeg;base64,{image_data}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=200,
                    temperature=0.3
                )

                description = response.choices[0].message.content.strip()

                analyses.append({
                    'frame_number': frame_data['frame_number'],
                    'timestamp': frame_data['timestamp'],
                    'description': description
                })

                # Clean up temp file
                try:
                    os.unlink(frame_data['temp_file'])
                except:
                    pass

            self.logger.info(f"Analyzed {len(analyses)} frames with VLM")

            return {
                'analyses': analyses,
                'model': 'gpt-4o',
                'total_analyzed': len(analyses)
            }

        except Exception as e:
            self.logger.error(f"VLM frame analysis failed: {e}")
            return None

    def _get_video_format(self, file_path: str) -> str:
        """Get video format"""
        ext = Path(file_path).suffix.lower()
        format_map = {
            '.mp4': 'MP4',
            '.avi': 'AVI',
            '.mov': 'MOV',
            '.mkv': 'MKV',
            '.flv': 'FLV',
            '.webm': 'WebM'
        }
        return format_map.get(ext, 'Unknown')

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"

    def _format_video_summary(self, video_info: dict) -> str:
        """Format video info into summary"""
        duration = video_info.get('duration_formatted', 'Unknown')
        resolution = video_info.get('resolution', 'Unknown')
        fps = video_info.get('fps', 0)

        return f"Video {resolution}, {fps:.1f} FPS, {duration} duration"

    def _format_frame_analysis_summary(self, frame_analysis: dict) -> str:
        """Format frame analysis into summary"""
        analyses = frame_analysis.get('analyses', [])
        if not analyses:
            return "No frame analysis available"

        return f"Analyzed {len(analyses)} key frames: {', '.join([a['description'][:30] + '...' for a in analyses[:3]])}"
