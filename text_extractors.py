"""
text_extractors.py
──────────────────
URLから本文を抽出する機能と、ファイルからテキストを読み込む機能。
"""


def extract_from_url(url: str) -> tuple:
    """
    URLから記事本文を抽出する。

    Args:
        url: 抽出対象のURL

    Returns:
        (タイトル, 本文) のタプル

    Raises:
        RuntimeError: 抽出に失敗した場合
    """
    try:
        import trafilatura
    except ImportError:
        raise RuntimeError(
            "trafilatura が未インストールです。"
            "pip install trafilatura を実行してください。"
        )

    # URLからHTMLを取得
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise RuntimeError(f"URLの取得に失敗しました: {url}")

    # メタデータ（タイトル）と本文を抽出
    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata and metadata.title else "untitled"

    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )

    if not text:
        raise RuntimeError(
            f"本文の抽出に失敗しました: {url}\n"
            "このサイトは本文抽出に対応していない可能性があります。"
        )

    return title, text


def extract_from_file(uploaded_file) -> tuple:
    """
    アップロードされたファイル（.txt, .md）からテキストを読み込む。

    Args:
        uploaded_file: Streamlitのアップロードファイルオブジェクト

    Returns:
        (ファイル名（拡張子なし）, 本文) のタプル
    """
    import os

    name = uploaded_file.name
    base_name = os.path.splitext(name)[0]

    raw_bytes = uploaded_file.read()

    # 文字コード自動判別（UTF-8 → Shift_JIS → EUC-JP の順で試す）
    for encoding in ['utf-8', 'utf-8-sig', 'shift_jis', 'cp932', 'euc-jp']:
        try:
            text = raw_bytes.decode(encoding)
            return base_name, text
        except UnicodeDecodeError:
            continue

    # 全部失敗したらerrors='replace'でUTF-8として読む
    text = raw_bytes.decode('utf-8', errors='replace')
    return base_name, text


def extract_from_pdf(uploaded_file) -> tuple:
    """
    アップロードされたPDFファイルからテキストを抽出する。

    Args:
        uploaded_file: Streamlitのアップロードファイルオブジェクト

    Returns:
        (ファイル名（拡張子なし）, 本文) のタプル
    """
    try:
        import pypdf
    except ImportError:
        raise RuntimeError(
            "pypdf が未インストールです。"
            "pip install pypdf を実行してください。"
        )

    import io
    import os

    name = uploaded_file.name
    base_name = os.path.splitext(name)[0]

    raw_bytes = uploaded_file.read()
    pdf_stream = io.BytesIO(raw_bytes)

    try:
        reader = pypdf.PdfReader(pdf_stream)
    except Exception as e:
        raise RuntimeError(f"PDFの読み込みに失敗しました: {e}")

    if len(reader.pages) == 0:
        raise RuntimeError("PDFにページが含まれていません")

    pages_text = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        except Exception:
            continue

    if not pages_text:
        raise RuntimeError(
            "PDFからテキストを抽出できませんでした。"
            "スキャンされた画像PDFの可能性があります（OCR未対応）。"
        )

    full_text = "\n\n".join(pages_text)
    return base_name, full_text
