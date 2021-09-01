function display_popup(msg){
    console.log(msg)
    $('.popup_msg').text(msg);
    $('.popup').show();
}

$(document).ready(function(){
    // close popup
    $('.popup_close').click(function(e){
        $(this).parent().hide();
    })

    // survey form
    $(".ajaxform").submit(function(e){
        var url = $(this).data("url");
        // prevent normal submit
        e.preventDefault();
        console.log("submitting")

        // store form for send to server
        var values = {};
        $.each($(this).serializeArray(), function(i, field) {
            // if already stored value, means need to store multiple
            if (field.name in values) {
                // if stored as string, now store as
                if (typeof(values[field.name])=="string") {
                    values[field.name] = [values[field.name], field.value];
                } else {
                    values[field.name].push(field.value);
                }
            } else {
                values[field.name] = field.value;
            }
        });
        console.log(values);
        $.ajax({
          type: 'POST',
          url: url,
          async: false,
          data: values,
          dataType: "json",
          error: function(data){
              console.log(data)
              display_popup(data.responseJSON['msg']);
          },
          success: function(data){
            // preemptively hide popup
            $('.popup').hide();

            // reset form after submit
            if ("redirect" in data){
              console.log(data['redirect'])
              window.location.href = data['redirect'];
            } else { 
                // load in next question
                $('.ajaxform > .question').html(data['question']);
                $('.ajaxform > .form_submit').val(data['submit']);
                $('#single_input').html(data['rendered_form']);
                // add question type
                if ($("input[name='qtype']").length){
                    var input = $("input[name='qtype']");
                } else {
                    var input = $("<input>")
                    $('.ajaxform').append(input);
                }
                input.attr("type", "hidden");
                input.attr("name", "qtype").val(data["type"]);
            }

          }
        });
    });
  
});