function getText(el) {
    return el.children[3].textContent;
}

function isRunning(text) {
    var result = (text.slice(0, 8) != 'Finished' && text != 'Dead' && text.slice(-4) != 'dead') && text != 'Error';
    // console.log('Result: ' + text + ' means ' + result);
    return result;
}

function statusUpdate () {
    var elements = $( "#process_list tr[data-sgid]" );
    var active = [];
    for (i = 0; i < elements.length; i++) {
        stext = getText(elements[i]);
        if (isRunning(stext)) {
            active.push(i);
        }
    }
    var i = 0;

    function updateNext() {
        if ( active.length == 0 ) {
            return false;
        }
        // console.log('Active rows: ' + active);
        var stillRunning = updateOneRow(elements[active[i]]);
        if (!stillRunning) {
            active.splice(i, 1);
        }
        else {
            i += 1;
        }
        if ( i >= active.length ) {
            i = 0;
        }
    }

    window.setInterval(updateNext, timeStep);
}

function updateOneRow (tr) {
    $.getJSON(statusRequestUrl + tr.getAttribute('data-sgid') + '/', function (data) {
        tr.children[3].textContent = data.status;
        tr.children[4].textContent = data.updated;
        if ( data.status == 'Postsearch processing' ) {
            tr.children[3].classList.add('postsearch');
        } else if ( data.status == 'Finished' ) {
            tr.children[3].classList.add('finished');
        } else if ( data.status == 'Error' || data.status == 'Finished with errors') {
            tr.children[3].classList.add('error');
        } else {
            var progress = data.done / data.total * 100;
            tr.children[3].style.backgroundSize = progress + '% 100%';
        }

    });

    return isRunning(getText(tr));
}


statusUpdate();
