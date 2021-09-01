function remove_opt(t){
  $(t).parent().remove();
}

$(document).ready(function(){
    // hide all forms
    $("form").hide();
    // show grid
    $("#grid").show();
    // show begin form
    $("#begin").show();

    $(".question_select").change(function(){
        // hide current form
        $("form").hide();
        // show selected form
        $("#" + $(this).val()).show();
    })

    $(".add_option").click(function(){
        var cls = $(this).data("name");
        console.log(cls);
        var btn = '<span><li><input type="text" name="'+cls+'" required></li><button type="button" onclick="remove_opt(this)">Remove (-)</button></span>';
        $(this).parent().append(btn);
    })

    $(".remove_opt").click(function(){
        // remove input and button
        $(this).parent().remove();
    })

    // on form submit, add question type from dropdown
    $("form").submit(function(){
        // if defined
        if ($(".question_select")){
            // add question type to form data
            var input = $("<input>")
              .attr("type", "hidden")
              .attr("name", "type").val($(".question_select").val());
            $(this).append(input);

            // add code to form data
            var input = $("<input>")
              .attr("type", "hidden")
              .attr("name", "code").val($("#code").val());
            $(this).append(input);

            // add question number to form data
            var input = $("<input>")
              .attr("type", "hidden")
              .attr("name", "qnum").val($("#qnum").val());
            $(this).append(input);
        }

    });
});