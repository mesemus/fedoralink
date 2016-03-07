$(document).ready(function() {

    // taken from http://stackoverflow.com/questions/819416/adjust-width-height-of-iframe-to-fit-with-content-in-it
    function autoResize(id){
        var newheight;
        var newwidth;

        if(document.getElementById){
            newheight = document.getElementById(id).contentWindow.document .body.scrollHeight;
            newwidth = document.getElementById(id).contentWindow.document .body.scrollWidth;
        }

        newheight += 20;

        document.getElementById(id).height = (newheight) + "px";
        document.getElementById(id).width = (newwidth) + "px";
    }

    function edit_link(ev) {
        var grp = $(ev.target).parents('.input-group');
        var inp = grp.find('input');

        var iframe = $('<iframe id="linked-field-selector" src="' + inp.attr('data-chooser') + '"></iframe>');
        iframe.on('load', function() {
            autoResize('linked-field-selector');
        });

        BootstrapDialog.show({
            title: 'Select value',
            size: BootstrapDialog.SIZE_WIDE,
            message: iframe
        });

    }



    $(document).on('click', '.linked-field-label', edit_link);
    $(document).on('click', '.linked-field-button', edit_link);
});