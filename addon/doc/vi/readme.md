# NVDA Bật âm thanh

* Tác giả: Oleksandr Gryshchenko
* Phiên bản: 1.3
* Tải về [phiên bản chính thức][1]
* Tải về [phiên bản thử nghiệm][2]

Add-on này kiểm tra trạng thái âm thanh hệ thống của Windows khi khởi động NVDA. Nếu nhận thấy rằng âm thanh bị tắt thì add-on sẽ  bật nó lên.
Add-on cũng kiểm tra trạng thái của bộ phát âm. Nếu có trục trặc với việc gọi chạy nó, add-on sẽ nỗ lực gọi bộ đọc đó lênvới các thiết lập trong cài đặt của NVDA.
Một tính năng bổ sung nữa là khả năng điều chỉnh âm lượng của thiết bị âm thanh chính và độc lập với các chương trình  đang chạy bằng phím tắt.

## Hộp thoại cài đặt Add-on
Hiện tại, có các tùy chọn sau đây trong hộp thoại cài đặt Add-on:
1. Tùy chọn cho phép bật âm thanh hệ thống với mức âm lượng lớn nhất khi khởi động NVDA.
2. Mức âm lượng tối thiểu của Windows để áp dụng việc tăng âm lượng. Thanh trượt này cho phép bạn chọn ngưỡng âm thanh cho  add-on.
Nếu mức âm lượng nhỏ hơn giá trị thiết lập ở đây, nó sẽ được tăng lên ở lần khởi động NVDA tiếp theo.
Còn nếu mức âm lượng lớn hơn giá trị được thiết lập ở đây, nó sẽ không bị thay đổi khi bạn khởi động lại NVDA.
Và dĩ nhiên,, nếu âm thanh đã bị tắt trước đó, khi khởi động lại, add-on sẽ bật nó lên.

3. Các hộp kiểm sau đây cho phép bật khởi động lại trình điều khiển của bộ đọc.
Việc này chỉ thực hiện khi nhận thấy rằng NVDA khởi động mà không khởi động trình điều khiển bộ đọc.

4. Ở trường này, bạn có thể thiết lập số lần  nỗ lực khởi động lại trình điều khiển bộ đọc. Việc này được thực hiện theo chu kì với mỗi lần cách nhau 1 giây.

5. Hộp kiểm tiếp theo bật / tắt việc phát âm thanh khởi động  khi hoàn thành việc khởi động lại trình điều khiển bộ đọc.

## Điều chỉnh mức độ âm thanh
Add-on này cho phép bạn chỉnh âm lượng thiết bị chính của Windows độc lập với các chương trình đang chạy.
Để làm điều này, dùng phím tắt NVDA+Windows+ các phím mũi tên.
Tính năng này hoạt động tương tự với vòng thiết lập tham số của NVDA. Dùng mũi tên trái / phải để chọn thiết bị hay ứng dụng, rồi dùng mũi tên lên / xuống để điều chỉnh âm lượng cho thành phần đã chọn.
Nếu chỉnh âm lượng thành 0 cho một chương trình nhất định và bấm mũi tên xuống một lần nữa, âm thanh từ thành phần này sẽ bị tắt.

Lưu ý: danh sách các nguồn âm thanh sẽ thay đổi tùy thuộc vào các chương trình đang chạy.

## Các thay đổi

### Phiên bản 1.3
* Thêm khả năng điều khiển âm thanh của thiết bị chính độc lập với các chương trình khác đang chạy;
* Cập nhật bản phiên dịch tiếng Việt (cảm ơn Đặng Mạnh Cường);
* Đã thêm bản phiên dịch tiếng Thổ Nhĩ Kỳ (cảm ơn Cagri Dogan);
* Đã thêm bản phiên dịch tiếng Ý (cảm ơn Christianlm); 
* Cập nhật bản phiên dịch tiếng Ukraina;
* Cập nhật tập tin Readme.

### Phiên bản 1.2
* Chuyển sang dùng **pycaw** module thay cho **Windows Sound Manager**;
* Thêm âm thanh khởi động khi audio đã được add-on bật lên.

### Phiên bản 1.1
* Thêm hộp thoại cài đặt add-on;
* Cập nhật bản dịch tiếng Ukraina.

### Phiên bản 1.0.1
* Thực hiện lặp đi lặp lại việc nỗ lực bật trình điều khiển bộ đọc trong trường hợp bị lỗi khi được gọi;
* Dịch ra tiếng Việt bởi Đặng Mạnh Cường;
* Thêm bản dịch tiếng Ugraina.

### Phiên bản 1.0. Thực hiện tính năng
Add-on sử dụng một module của bên thứ ba [Windows Sound Manager][2].

## Tùy biến NVDA Bật âm thanh
Bạn có thể tạo bản sao (clone) cho add-on này để thực hiện các tùy biến cho nó.

### Các thư viện phụ thuộc của bên thứ ba
Chúng có thể được cài đặt với pip:
- markdown
- scons
- python-gettext

### Để đóng gói và phân phối add-on:
1. Mở một ứng dụng dòng lệnh, điều hướng đến thư mục gốc của kho add-on này
2. Gõ lệnh **scons**. Gói add-on sẽ được tạo ở thư mục hiện tại nếu không có lỗi xảy ra.

[1]: 
[2]: 
