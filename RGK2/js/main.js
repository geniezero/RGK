
  function openuRL(url) {
  	$("#content").addClass('fadeOut');
	$("#content").append('<img src="./img/ajax-loader_dark.gif"/>');	
		$.ajax({
			url: url,	
			type: 'POST',	
			cache: false,
			success: function (data) {	
				$("#content").removeClass('fadeOut');
				$("#content").hide();	
				$("#content").html(data);
				$("#content").show('slow',function(){$(this).addClass('animated fadeInUp');});	
				}		
			});
	  return false;
	}	 
