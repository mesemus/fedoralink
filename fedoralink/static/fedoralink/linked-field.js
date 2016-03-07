$(document).ready(function() {

    // taken from http://stackoverflow.com/questions/819416/adjust-width-height-of-iframe-to-fit-with-content-in-it
    function autoResize(id) {
        var newheight;
        var newwidth;

        if (document.getElementById) {
            newheight = document.getElementById(id).contentWindow.document.body.scrollHeight;
            newwidth = document.getElementById(id).contentWindow.document.body.scrollWidth;
        }

        newheight += 20;

        document.getElementById(id).height = (newheight) + "px";
        document.getElementById(id).width = (newwidth) + "px";
    }

    var dlg;
    var grp;
    var inp;
    var lbl;
    var labelurl;

    function fetch_data(lbl, url) {
        $.ajax(url).then(function(data) {
            data = $('<p>' + data + '</p>');
            lbl.text(data.text());
        });
    }

    function edit_link(ev) {
        grp = $(ev.target).parents('.input-group');
        lbl = grp.find('.linked-field-label');
        inp = grp.find('input');
        labelurl = inp.attr('data-label-url');
        labelurl = labelurl.substr(0, labelurl.lastIndexOf('/')+1);

        var iframe = $('<iframe id="linked-field-selector" src="' + inp.attr('data-chooser') + '"></iframe>');
        iframe.on('load', function () {
            autoResize('linked-field-selector');
        });

        dlg = BootstrapDialog.show({
            title: 'Select value',
            size: BootstrapDialog.SIZE_WIDE,
            message: iframe
        });

    }

    function remove_link(ev) {
        grp = $(ev.target).parents('.input-group');
        lbl = grp.find('.linked-field-label');
        inp = grp.find('input');

        lbl.text('');
        inp.val('');
    }

    function fetch_label() {
        grp = $(this).parents('.input-group');
        lbl = grp.find('.linked-field-label');
        inp = grp.find('input');
        labelurl = inp.attr('data-label-url');
        if (labelurl.lastIndexOf('/') != labelurl.length-1) {
            fetch_data(lbl, labelurl);
        }
    }
    $('[data-label-url]').each(fetch_label);

    // Listen to message from child window

    var eventMethod = window.addEventListener ? "addEventListener" : "attachEvent";
    var eventer = window[eventMethod];
    var messageEvent = eventMethod == "attachEvent" ? "onmessage" : "message";

    eventer(messageEvent, function (e) {
        var key = e.message ? "message" : "data";
        var data = JSON.parse(e[key]);
        dlg.close();
        inp.val(data[0]);
        fetch_data(lbl, labelurl + data[1]);
    });

    function pass_link(ev) {
        var target = $(ev.target);
        target = target.parents('a');
        var link = [
            target.attr('data-link-location'),
            target.attr('data-link-id')
        ];
        parent.postMessage(JSON.stringify(link), "*");
    }

    $(document).on('click', '.linked-field-label', edit_link);
    $(document).on('click', '.linked-field-button', edit_link);
    $(document).on('click', '.linked-field-button-remove', remove_link);
    $(document).on('click', '.linked-field-pass-link', pass_link);

});