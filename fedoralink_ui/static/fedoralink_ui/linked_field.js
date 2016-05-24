$(document).ready(function() {
    function link_event(ev) {
        var container = $(ev.target).parents('.fedoralink_ui-linked-field');
        var body = container.find('.modal-body');
        var dlg = container.find('.link-dialog');

        body.empty();
        dlg.modal('show');

        var link_url = container.attr('data-link-url');

        var iframe = $('<iframe>').attr('src', link_url).addClass('fedoralink_ui-link-select-dialog');
        iframe.on('load', function(ev) {
            var obj = ev.target;
            obj.style.height = obj.contentWindow.document.body.scrollHeight + 'px';
        });
        body.append(iframe);

        $(window).off("message onmessage");

        $(window).on("message onmessage", function(e) {
            var data = JSON.parse(e.originalEvent.data);
            switch(data.action) {
                case 'link-target':
                    if (data.status == 'ok') {
                        container.find('input').val(data.id);
                        container.find('.link-label').text(data.title);
                    }
                    dlg.modal('hide');
                    break;
            }
        });

        ev.stopImmediatePropagation();
    }
    $(document).on('click', '.fedoralink_ui-linked-field .link-label', function(ev) {
        link_event(ev);
    });
    $(document).on('click', '.fedoralink_ui-linked-field .link-button', function(ev) {
        link_event(ev);
    });
});