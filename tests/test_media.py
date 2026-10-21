from pathlib import Path

import pytest

from youtube_read_mcp import media
from youtube_read_mcp.config import Settings

VID="dQw4w9WgXcQ"


def test_frame_and_clip_validation(tmp_path):
    cfg=Settings(data_dir=tmp_path)
    with pytest.raises(ValueError):
        media.extract_frames(VID,[],cfg=cfg)
    with pytest.raises(ValueError):
        media.extract_frames(VID,list(range(13)),cfg=cfg)
    with pytest.raises(ValueError):
        media.extract_frames(VID,[10],width=20,cfg=cfg)
    with pytest.raises(ValueError):
        media.extract_clip(VID,5,duration_seconds=121,cfg=cfg)
    with pytest.raises(ValueError):
        media.download_media(VID,mode="invalid",cfg=cfg)


def test_download_rejects_bad_quality(tmp_path):
    with pytest.raises(ValueError):
        media.download_media(VID,mode="video",quality="ultra-10000",cfg=Settings(data_dir=tmp_path))
