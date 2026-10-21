from youtube_read_mcp.core import normalize_video_id, video_url


def test_normalize_video_id_variants():
    video_id = "dQw4w9WgXcQ"
    assert normalize_video_id(video_id) == video_id
    assert normalize_video_id(f"https://www.youtube.com/watch?v={video_id}&t=1") == video_id
    assert normalize_video_id(f"https://youtu.be/{video_id}?si=abc") == video_id
    assert normalize_video_id(f"https://www.youtube.com/shorts/{video_id}") == video_id
    assert normalize_video_id(f"https://www.youtube.com/embed/{video_id}") == video_id
    assert video_url(video_id).endswith(video_id)


def test_invalid_video_id_rejected():
    try:
        normalize_video_id("not-a-youtube-video")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
