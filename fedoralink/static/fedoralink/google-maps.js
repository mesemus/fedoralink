$(document).ready(function() {
    $(document).on('click', '.google-map-input-button', function(ev) {
        BootstrapDialog.show({
            size: BootstrapDialog.SIZE_WIDE,
            title: 'Click on the map to select location',
            message: '<div id="edit-map" style="width: 550px;height: 400px;"></div>',
            onshown: function(dialogRef){
                var content = $(dialogRef.getModal()).find('.bootstrap-dialog-message');
                var map_el = $('#edit-map');
                map_el.css({
                    width: content.width(),
                    height: content.width() * 3/5
                });
                var map = new google.maps.Map(document.getElementById('edit-map'), {
                    center: {lat: 48.965955, lng: 19.5797498},
                    zoom: 11
                });
                var marker = null;
                function placeMarkerAndPanTo(latLng, map) {
                    if (marker) {
                        marker.setMap(null);
                    }
                    marker = new google.maps.Marker({
                        position: latLng,
                        map: map
                    });
                    map.panTo(latLng);
                }
                map.addListener('click', function(e) {
                    placeMarkerAndPanTo(e.latLng, map);
                });

                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(position) {
                      var pos = {
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                      };
                      map.setCenter(pos);
                    });
                }
            },
            buttons: [{
                label: 'Save location',
                cssClass: 'btn-primary',
                action: function(dialogItself){
                    dialogItself.close();
                }
            },
            {
                label: 'Close',
                action: function(dialogItself){
                    dialogItself.close();
                }
            }]
        });
    });
});
