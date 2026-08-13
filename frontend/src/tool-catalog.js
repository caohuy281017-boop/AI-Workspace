'use strict';

(function exposeToolCatalog(root, factory) {
  const catalog = factory();
  if (typeof module === 'object' && module.exports) module.exports = catalog;
  root.AIWorkspaceToolCatalog = catalog;
})(typeof globalThis !== 'undefined' ? globalThis : window, function buildToolCatalog() {
  const groups = [
    {
      id: 'writing',
      title: 'Soạn thảo & chỉnh sửa văn bản',
      description: 'Sửa nhanh nội dung lấy từ Word, PDF, email hoặc website trước khi gửi và xuất bản.',
    },
    {
      id: 'lists',
      title: 'Làm sạch danh sách',
      description: 'Chuẩn hóa danh sách khách hàng, sản phẩm hoặc công việc trước khi đưa vào Excel.',
    },
    {
      id: 'data',
      title: 'Chuyển đổi & kiểm tra dữ liệu',
      description: 'Đổi dữ liệu giữa các định dạng phổ biến và tìm nhanh thông tin nằm trong văn bản dài.',
    },
    {
      id: 'web',
      title: 'Nội dung web & chia sẻ',
      description: 'Chuẩn bị đường dẫn, nội dung kỹ thuật và dữ liệu cần gửi qua website hoặc hệ thống khác.',
    },
  ];

  const tools = [
    {
      id: 'word-count', group: 'writing', icon: '123', title: 'Kiểm tra độ dài bài viết',
      description: 'Đếm từ, ký tự, số dòng và ước tính thời gian cần để đọc hết nội dung.',
      useWhen: 'Dùng khi viết bài SEO, báo cáo, email hoặc nội dung có giới hạn độ dài.',
      example: 'Bài viết dài → 1.250 từ · khoảng 6 phút đọc',
      inputLabel: 'Bài viết cần kiểm tra', outputLabel: 'Thống kê độ dài',
      placeholder: 'Dán bài viết, email hoặc nội dung báo cáo vào đây...',
      keywords: 'đếm chữ số từ bài viết seo thời gian đọc',
    },
    {
      id: 'clean-text', group: 'writing', icon: '¶', title: 'Dọn văn bản lỗi khoảng trắng',
      description: 'Xóa khoảng trắng thừa, dòng trống dư và khoảng cách lộn xộn trong văn bản.',
      useWhen: 'Dùng khi nội dung sao chép từ PDF, website hoặc email bị xuống dòng và giãn cách xấu.',
      example: 'Văn bản lộn xộn → đoạn văn gọn, dễ đọc',
      inputLabel: 'Văn bản đang bị lỗi', outputLabel: 'Văn bản đã làm sạch',
      placeholder: 'Dán nội dung bị thừa khoảng trắng hoặc dòng trống...',
      keywords: 'làm sạch văn bản khoảng trắng xuống dòng pdf word',
    },
    {
      id: 'case-converter', group: 'writing', icon: 'Aa', title: 'Đổi chữ hoa và chữ thường',
      description: 'Chuyển toàn bộ nội dung sang chữ hoa, chữ thường, kiểu tiêu đề hoặc kiểu câu.',
      useWhen: 'Dùng khi tiêu đề, danh sách tên hoặc nội dung nhập liệu bị viết hoa thường không đồng nhất.',
      example: 'cÔNG TY aBC → Công Ty Abc',
      inputLabel: 'Nội dung cần đổi kiểu chữ', outputLabel: 'Nội dung sau khi chuyển',
      placeholder: 'Dán tiêu đề, tên sản phẩm hoặc đoạn văn...',
      keywords: 'chữ hoa chữ thường title case tiêu đề',
    },
    {
      id: 'remove-accents', group: 'writing', icon: 'Ă', title: 'Bỏ dấu tiếng Việt',
      description: 'Chuyển chữ tiếng Việt có dấu thành không dấu mà vẫn giữ nguyên từ và câu.',
      useWhen: 'Dùng khi hệ thống cũ, mã nội bộ hoặc tên file không chấp nhận ký tự tiếng Việt.',
      example: 'Công ty Ánh Dương → Cong ty Anh Duong',
      inputLabel: 'Nội dung tiếng Việt có dấu', outputLabel: 'Nội dung không dấu',
      placeholder: 'Dán tên, địa chỉ hoặc nội dung tiếng Việt...',
      keywords: 'xóa bỏ dấu tiếng việt tên file mã',
    },
    {
      id: 'html-to-text', group: 'writing', icon: '</>', title: 'Lấy chữ từ mã HTML',
      description: 'Loại bỏ các thẻ HTML và chỉ giữ lại phần nội dung mà người đọc nhìn thấy.',
      useWhen: 'Dùng khi sao chép nội dung từ trình soạn thảo web nhưng nhận về cả mã HTML.',
      example: '<p>Xin chào</p> → Xin chào',
      inputLabel: 'Mã HTML đầu vào', outputLabel: 'Văn bản có thể đọc',
      placeholder: 'Dán đoạn HTML cần lấy nội dung chữ...',
      keywords: 'html sang text lấy chữ bỏ thẻ website',
    },
    {
      id: 'markdown-to-text', group: 'writing', icon: 'M↓', title: 'Lấy chữ từ Markdown',
      description: 'Bỏ dấu tiêu đề, liên kết, danh sách và ký hiệu Markdown để lấy văn bản thuần.',
      useWhen: 'Dùng khi nội dung từ GitHub, AI hoặc hệ thống ghi chú còn chứa nhiều ký hiệu Markdown.',
      example: '**Báo cáo** [tháng 8](link) → Báo cáo tháng 8',
      inputLabel: 'Nội dung Markdown', outputLabel: 'Văn bản thuần',
      placeholder: 'Dán Markdown cần chuyển thành văn bản...',
      keywords: 'markdown sang text bỏ ký hiệu github ai',
    },
    {
      id: 'remove-duplicate-lines', group: 'lists', icon: '≠', title: 'Xóa dòng bị trùng',
      description: 'Giữ lại một lần xuất hiện của mỗi dòng và loại bỏ các dòng lặp lại trong danh sách.',
      useWhen: 'Dùng trước khi nhập danh sách email, mã hàng, khách hàng hoặc từ khóa vào Excel.',
      example: 'A · B · A · C → A · B · C',
      inputLabel: 'Danh sách có dòng trùng', outputLabel: 'Danh sách không trùng',
      placeholder: 'Mỗi mục đặt trên một dòng...',
      keywords: 'xóa trùng lọc trùng danh sách email khách hàng excel',
    },
    {
      id: 'sort-lines', group: 'lists', icon: 'A↓', title: 'Sắp xếp danh sách',
      description: 'Sắp xếp từng dòng theo A–Z, Z–A hoặc theo độ dài của nội dung.',
      useWhen: 'Dùng khi cần sắp tên, mã sản phẩm, từ khóa hoặc danh mục trước khi gửi và lưu.',
      example: 'Cam · Bưởi · An → An · Bưởi · Cam',
      inputLabel: 'Danh sách cần sắp xếp', outputLabel: 'Danh sách đã sắp xếp',
      placeholder: 'Dán danh sách, mỗi mục một dòng...',
      keywords: 'sắp xếp az za danh sách tên mã sản phẩm',
    },
    {
      id: 'reverse-lines', group: 'lists', icon: '↕', title: 'Đảo ngược thứ tự dòng',
      description: 'Đưa dòng cuối lên đầu và đảo ngược toàn bộ thứ tự hiện tại của danh sách.',
      useWhen: 'Dùng khi nhật ký, lịch sử hoặc danh sách đang được sắp từ cũ đến mới không đúng nhu cầu.',
      example: 'Dòng 1 · Dòng 2 · Dòng 3 → Dòng 3 · Dòng 2 · Dòng 1',
      inputLabel: 'Danh sách ban đầu', outputLabel: 'Danh sách đã đảo thứ tự',
      placeholder: 'Dán danh sách cần đảo thứ tự...',
      keywords: 'đảo dòng đảo danh sách cuối lên đầu',
    },
    {
      id: 'remove-empty-lines', group: 'lists', icon: '¶−', title: 'Xóa toàn bộ dòng trống',
      description: 'Loại bỏ các dòng không có nội dung để tạo thành danh sách liên tục và gọn hơn.',
      useWhen: 'Dùng khi dữ liệu sao chép từ Excel, PDF hoặc biểu mẫu bị xen nhiều dòng trống.',
      example: 'A · [trống] · B → A · B',
      inputLabel: 'Danh sách có dòng trống', outputLabel: 'Danh sách liền mạch',
      placeholder: 'Dán danh sách đang bị xen dòng trống...',
      keywords: 'xóa dòng trống danh sách excel pdf',
    },
    {
      id: 'number-lines', group: 'lists', icon: '1.', title: 'Đánh số từng dòng',
      description: 'Thêm số thứ tự tự động vào đầu từng dòng có nội dung trong danh sách.',
      useWhen: 'Dùng để tạo danh sách công việc, câu hỏi, sản phẩm hoặc các bước hướng dẫn.',
      example: 'Mua hàng · Gọi khách → 1. Mua hàng · 2. Gọi khách',
      inputLabel: 'Danh sách chưa đánh số', outputLabel: 'Danh sách có số thứ tự',
      placeholder: 'Dán danh sách cần đánh số...',
      keywords: 'đánh số thứ tự danh sách công việc',
    },
    {
      id: 'join-split-lines', group: 'lists', icon: '⇥', title: 'Ghép hoặc tách danh sách',
      description: 'Ghép nhiều dòng bằng dấu phẩy, dấu chấm phẩy hoặc tách một dòng thành nhiều dòng.',
      useWhen: 'Dùng khi chuyển danh sách giữa Excel, email, phần mềm nhập liệu và nội dung văn bản.',
      example: 'A · B · C → A, B, C',
      inputLabel: 'Danh sách cần chuyển', outputLabel: 'Danh sách sau khi ghép hoặc tách',
      placeholder: 'Dán danh sách nhiều dòng hoặc chuỗi cách nhau bằng dấu phẩy...',
      keywords: 'nối dòng tách dòng dấu phẩy excel danh sách',
    },
    {
      id: 'text-workflow', group: 'lists', icon: '✓', title: 'Chuẩn hóa danh sách một lần',
      description: 'Kết hợp làm sạch khoảng trắng, xóa dòng trùng và sắp xếp trong một thao tác.',
      useWhen: 'Dùng khi nhận một danh sách thô và muốn làm sạch hoàn toàn trước khi đưa vào Excel.',
      example: 'Danh sách thô, trùng, lệch → danh sách sạch và có thứ tự',
      inputLabel: 'Danh sách thô', outputLabel: 'Danh sách đã chuẩn hóa',
      placeholder: 'Dán danh sách khách hàng, sản phẩm hoặc từ khóa...',
      keywords: 'workflow dọn danh sách khách hàng chuẩn hóa danh sách làm sạch xóa trùng sắp xếp',
    },
    {
      id: 'json-format', group: 'data', icon: '{}', title: 'Kiểm tra và trình bày JSON',
      description: 'Kiểm tra JSON có hợp lệ không và căn lề dữ liệu để con người dễ đọc hơn.',
      useWhen: 'Dùng khi nhận dữ liệu từ API hoặc phần mềm và cần tìm nhanh cấu trúc hay lỗi cú pháp.',
      example: '{"name":"An"} → JSON được xuống dòng và căn lề',
      inputLabel: 'Dữ liệu JSON', outputLabel: 'JSON đã kiểm tra và căn lề',
      placeholder: 'Dán JSON cần kiểm tra...',
      keywords: 'json format kiểm tra lỗi api dữ liệu',
    },
    {
      id: 'json-minify', group: 'data', icon: '{·}', title: 'Thu gọn dữ liệu JSON',
      description: 'Xóa xuống dòng và khoảng trắng không cần thiết để JSON ngắn gọn hơn khi truyền đi.',
      useWhen: 'Dùng trước khi lưu cấu hình, gửi dữ liệu qua API hoặc chèn JSON vào một trường văn bản.',
      example: 'JSON nhiều dòng → một dòng JSON gọn nhẹ',
      inputLabel: 'JSON đang có nhiều khoảng trắng', outputLabel: 'JSON đã thu gọn',
      placeholder: 'Dán JSON cần thu gọn...',
      keywords: 'json minify thu gọn một dòng api',
    },
    {
      id: 'csv-to-json', group: 'data', icon: 'C→J', title: 'Đổi bảng CSV sang JSON',
      description: 'Dùng hàng đầu làm tên cột và chuyển các hàng còn lại thành danh sách dữ liệu JSON.',
      useWhen: 'Dùng khi dữ liệu xuất từ Excel hoặc Google Sheets cần đưa vào API hay phần mềm khác.',
      example: 'name,email\nAn,a@b.com → danh sách JSON có tên và email',
      inputLabel: 'Bảng CSV', outputLabel: 'Dữ liệu JSON',
      placeholder: 'Dán CSV, hàng đầu tiên là tên các cột...',
      keywords: 'csv sang json excel google sheet api',
    },
    {
      id: 'extract-contacts', group: 'data', icon: '@', title: 'Lấy email, số điện thoại và link',
      description: 'Quét một đoạn văn bản dài để gom riêng email, số điện thoại hoặc đường dẫn website.',
      useWhen: 'Dùng khi cần lấy thông tin liên hệ từ danh sách khách hàng, email, báo cáo hoặc website.',
      example: 'Đoạn giới thiệu dài → danh sách email hoặc số điện thoại',
      inputLabel: 'Văn bản chứa thông tin liên hệ', outputLabel: 'Thông tin đã trích xuất',
      placeholder: 'Dán nội dung có email, số điện thoại hoặc đường dẫn...',
      keywords: 'trích xuất email số điện thoại url liên hệ khách hàng',
    },
    {
      id: 'slug', group: 'web', icon: '#', title: 'Tạo đường dẫn từ tiêu đề',
      description: 'Chuyển tiêu đề tiếng Việt thành đoạn đường dẫn ngắn, không dấu và thân thiện với SEO.',
      useWhen: 'Dùng khi đăng bài website, đặt URL sản phẩm hoặc tạo tên file thống nhất.',
      example: 'Hướng dẫn dùng AI → huong-dan-dung-ai',
      inputLabel: 'Tiêu đề hoặc tên nội dung', outputLabel: 'Đường dẫn slug',
      placeholder: 'Nhập tiêu đề bài viết hoặc tên sản phẩm...',
      keywords: 'slug đường dẫn seo url tiêu đề không dấu',
    },
    {
      id: 'url-encode', group: 'web', icon: '%', title: 'Mã hóa nội dung trong URL',
      description: 'Mã hóa ký tự đặc biệt để đặt an toàn trong đường dẫn hoặc giải mã về nội dung ban đầu.',
      useWhen: 'Dùng khi đường dẫn có dấu cách, tiếng Việt, ký hiệu đặc biệt hoặc tham số bị lỗi.',
      example: 'xin chào? → xin%20ch%C3%A0o%3F',
      inputLabel: 'Nội dung hoặc URL cần xử lý', outputLabel: 'Kết quả mã hóa hoặc giải mã',
      placeholder: 'Dán nội dung hoặc phần URL cần mã hóa/giải mã...',
      keywords: 'url encode decode mã hóa đường dẫn ký tự đặc biệt',
    },
    {
      id: 'base64', group: 'web', icon: '64', title: 'Mã hóa văn bản Base64',
      description: 'Chuyển văn bản UTF-8 thành chuỗi Base64 hoặc giải mã chuỗi Base64 về nội dung gốc.',
      useWhen: 'Dùng khi hệ thống yêu cầu dữ liệu Base64; đây là mã hóa biểu diễn, không phải bảo mật.',
      example: 'Xin chào → WGluIGNow6Bv',
      inputLabel: 'Văn bản hoặc chuỗi Base64', outputLabel: 'Kết quả chuyển đổi',
      placeholder: 'Dán văn bản hoặc chuỗi Base64...',
      keywords: 'base64 encode decode utf8 mã hóa giải mã',
    },
  ];

  function normalizeSearchText(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/đ/g, 'd')
      .replace(/Đ/g, 'D')
      .toLocaleLowerCase('vi')
      .trim();
  }

  function rankTools(sourceTools, query) {
    const normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) return [...sourceTools];

    const queryTokens = normalizedQuery.split(/\s+/).filter(token => token.length > 1);
    const ranked = sourceTools
      .map((tool, index) => {
        const title = normalizeSearchText(tool.title);
        const keywords = normalizeSearchText(tool.keywords);
        const description = normalizeSearchText(tool.description);
        const useWhen = normalizeSearchText(tool.useWhen);
        const example = normalizeSearchText(tool.example);
        const placeholder = normalizeSearchText(tool.placeholder);
        let score = 0;
        if (title === normalizedQuery) score += 200;
        if (title.includes(normalizedQuery)) score += 100;
        if (keywords.includes(normalizedQuery)) score += 70;
        if (description.includes(normalizedQuery)) score += 30;
        if (useWhen.includes(normalizedQuery)) score += 15;
        if (example.includes(normalizedQuery)) score += 5;
        for (const token of queryTokens) {
          if (title.includes(token)) score += 18;
          if (keywords.includes(token)) score += 12;
          if (description.includes(token)) score += 8;
          if (useWhen.includes(token)) score += 4;
          if (placeholder.includes(token)) score += 4;
          if (example.includes(token)) score += 2;
        }
        return { tool, index, score };
      })
      .filter(item => item.score > 0)
      .sort((left, right) => right.score - left.score || left.index - right.index);

    const bestScore = ranked[0]?.score || 0;
    const relevanceFloor = Math.max(5, bestScore * 0.2);
    return ranked.filter(item => item.score >= relevanceFloor).map(item => item.tool);
  }

  return { groups, tools, rankTools };
});
