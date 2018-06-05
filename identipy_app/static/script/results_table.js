$(".header").width($(".dt").width());
$header = $('.header');
var x = $header.find('td');

$('.mega').on('scroll',function(){$header.css('top',$(this).scrollTop());});
$(".header tr th").each(function (i){
       $(this).width($($(".dt tr:first th")[i]).width());
})

