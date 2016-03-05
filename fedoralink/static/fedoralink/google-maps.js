$(document).ready(function () {
    $(document).on('click', '.google-map-input-button', function (ev) {
        var lastLatLong = [];
        var inp = $(ev.target).parents('.input-group').find('input');
        lastLatLong = inp.val();
        if (lastLatLong) {
            if (lastLatLong.indexOf(';')>=0) {
                lastLatLong = lastLatLong.split(';')
            } else {
                lastLatLong = lastLatLong.split(',')
            }
        console.log(lastLatLong);
            lastLatLong = lastLatLong.map(function(el) {
                return parseFloat(el);
            });
        } else {
            lastLatLong = [48.965955, 19.5797498]
        }

        BootstrapDialog.show({
            size: BootstrapDialog.SIZE_WIDE,
            title: 'Click on the map to select location',
            message: '<input id="pac-input" class="controls" type="text" placeholder="Search Box" autocomplete="on"><div id="edit-map" style="width: 550px;height: 400px;"></div>',
            onshown: function (dialogRef) {
                var content = $(dialogRef.getModal()).find('.bootstrap-dialog-message');
                var map_el = $('#edit-map');
                map_el.css({
                    width: content.width(),
                    height: content.width() * 3 / 5
                });
                var map = new google.maps.Map(document.getElementById('edit-map'), {
                    center: {lat: lastLatLong[0], lng: lastLatLong[1]},
                    zoom: 11
                });
                var marker = null;

                function placeMarkerAndPanTo(latLng, map, store) {
                    if (marker) {
                        marker.setMap(null);
                    }
                    marker = new google.maps.Marker({
                        position: latLng,
                        map: map
                    });
                    map.panTo(latLng);
                    if (store)
                        lastLatLong = [latLng.lat(), latLng.lng()];
                }

                map.addListener('click', function (e) {
                    placeMarkerAndPanTo(e.latLng, map, true);
                });

                placeMarkerAndPanTo({lat: lastLatLong[0], lng: lastLatLong[1]}, map, false);
                //
                //if (navigator.geolocation) {
                //    navigator.geolocation.getCurrentPosition(function (position) {
                //        var pos = {
                //            lat: position.coords.latitude,
                //            lng: position.coords.longitude
                //        };
                //        map.setCenter(pos);
                //    });
                //}


                // Create the search box and link it to the UI element.
                var input = document.getElementById('pac-input');
                var searchBox = new google.maps.places.SearchBox(input);
                map.controls[google.maps.ControlPosition.TOP_LEFT].push(input);

                var autocomplete = new google.maps.places.Autocomplete(input);
                autocomplete.bindTo('bounds', map);

                autocomplete.addListener('place_changed', function () {
                    var place = autocomplete.getPlace();
                    if (!place.geometry) {
                        window.alert("Autocomplete's returned place contains no geometry");
                        return;
                    }

                    map.setCenter(place.geometry.location);
                    map.setZoom(17);  // Why 17? Because it looks good.
                });


                // Bias the SearchBox results towards current map's viewport.
                map.addListener('bounds_changed', function () {
                    searchBox.setBounds(map.getBounds());
                });

                var markers = [];
                // Listen for the event fired when the user selects a prediction and retrieve
                // more details for that place.
                searchBox.addListener('places_changed', function () {
                    var places = searchBox.getPlaces();

                    if (places.length == 0) {
                        return;
                    }

                    // Clear out the old markers.
                    markers.forEach(function (marker) {
                        marker.setMap(null);
                    });
                    markers = [];

                    // For each place, get the icon, name and location.
                    var bounds = new google.maps.LatLngBounds();
                    places.forEach(function (place) {
                        var icon = {
                            url: place.icon,
                            size: new google.maps.Size(71, 71),
                            origin: new google.maps.Point(0, 0),
                            anchor: new google.maps.Point(17, 34),
                            scaledSize: new google.maps.Size(25, 25)
                        };

                        // Create a marker for each place.
                        markers.push(new google.maps.Marker({
                            map: map,
                            icon: icon,
                            title: place.name,
                            position: place.geometry.location
                        }));

                        if (place.geometry.viewport) {
                            // Only geocodes have viewport.
                            bounds.union(place.geometry.viewport);
                        } else {
                            bounds.extend(place.geometry.location);
                        }
                    });
                    map.fitBounds(bounds);
                });

            },
            buttons: [{
                label: 'Save location',
                cssClass: 'btn-primary',
                action: function (dialogItself) {
                    inp.val(lastLatLong[0] + "," + lastLatLong[1]);
                    $.ajax("https://maps.googleapis.com/maps/api/geocode/json?latlng=" +
                        lastLatLong[0] + "," + lastLatLong[1] + "&key=" + google_key).
                        then(function(data) {
                        dialogItself.close();
                        if (data['status'] == 'OK') {
                            var results = data['results'];
                            if (results.length>0) {
                                var res = results[0];
                                var components = {};
                                $(res['address_components']).each(function() {
                                    var val = this['long_name'];
                                    $(this['types']).each(function() {
                                        components[String(this)] = val;
                                    });
                                });

                                function c(x) {
                                    if (x) return x;
                                    return '';
                                }

                                BootstrapDialog.confirm('The map server returned the following address. Use it?<br><br>' +
                                    c(components['route']) + " " + c(components['street_number']) + "<br>" +
                                    c(components["sublocality"]) + "<br>" +
                                    c(components["postal_code"]) + " " + c(components["locality"]) + "<br>" +
                                    c(components["country"]),
                                    function(result) {
                                        if (result) {
                                            if (components['route']) {
                                                $('#id_street').val(components['route']);
                                            } else {
                                                $('#id_street').val('');
                                            }
                                            if (components['street_number']) {
                                                $('#id_house_number').val(components['street_number']);
                                            } else {
                                                $('#id_house_number').val('');
                                            }
                                            if (components['postal_code']) {
                                                $('#id_zip').val(components['postal_code']);
                                            } else {
                                                $('#id_zip').val('');
                                            }
                                            if (components['sublocality']) {
                                                $('#id_region').val(components['sublocality']);
                                            } else {
                                                $('#id_region').val('');
                                            }
                                            if (components['locality']) {
                                                $('#id_town').val(components['locality']);
                                            } else {
                                                $('#id_town').val('');
                                            }
                                            if (components['country']) {
                                                $('#id_country').val(components['country']);
                                            } else {
                                                $('#id_country').val('');
                                            }
                                        }
                                    });
                            } else {
                                BootstrapDialog.alert("Map server did not return street data, please fill them yourself.");
                            }
                        } else {
                            BootstrapDialog.alert("Can not convert map coordinates to street data, please fill them yourself.");
                        }
                    });
                }
            },
                {
                    label: 'Close',
                    action: function (dialogItself) {
                        dialogItself.close();
                    }
                }]
        });
    });
});
