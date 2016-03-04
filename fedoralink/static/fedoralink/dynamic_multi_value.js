$(document).ready(function() {
    $(document).on('click', '.dynamic-multivalue-field-remove', function(ev) {
        console.log(this);
        var field_container = $(this).parents('.dynamic-multivalue-child-field');
        var parent = field_container.parent();
        if (parent.find('.dynamic-multivalue-child-field').length == 1) {
            return;
        }
        var removed_id = field_container.find('[id]').attr('id');
        removed_id = parseInt(removed_id.replace(/^.*_/, ''));

        parent.find('[id]').each(function() {
            var el = $(this);
            var id = el.attr('id');
            var curid = parseInt(id.replace(/^.*_/, ''));
            if (curid>removed_id) {
                el.attr('id', id.replace(/_[0-9]+$/, '_' + (curid-1)));
            }
        });

        parent.find('[name]').each(function() {
            var el = $(this);
            var id = el.attr('name');
            var curid = parseInt(id.replace(/^.*_/, ''));
            if (curid>removed_id) {
                el.attr('name', id.replace(/_[0-9]+$/, '_' + (curid-1)));
            }
        });

        field_container.remove();
    });

    $(document).on('click', '.dynamic-multivalue-field-add', function(ev) {
        var container = $(this).parents('.dynamic-multivalue-field-group');
        var fld = container.find('.dynamic-multivalue-child-field').first();
        var cloned = fld.clone(true);
        var ids = [];
        container.find('[id]').each(function() {
            var el = $(this);
            var id = el.attr('id');
            if (/^.*_[0-9]+$/.test(id)) {
                ids.push(parseInt(id.replace(/^.*_/, '')));
            }
        });
        var new_id = Math.max.apply(null, ids) + 1;
        cloned.find('[id]').each(function() {
            var el = $(this);
            var id = el.attr('id');
            el.attr('id', id.replace(/_[0-9]+$/, '_' + new_id));
        });
        cloned.find('[name]').each(function() {
            var el = $(this);
            var id = el.attr('name');
            el.attr('name', id.replace(/_[0-9]+$/, '_' + new_id));
        });
        cloned.find('input').attr('value', '');
        cloned.find('textarea').text();
        cloned.insertBefore($(this));
    });
});