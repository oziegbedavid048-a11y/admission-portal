/*
 * The blur tool on the landing page review screen in the admin.
 *
 * The admin chooses an image or a PDF; it is shown here (a PDF as its first
 * page, rendered by the server and not kept), the admin drags boxes over
 * anything private, and each box is pixelated and blurred. On save, only that
 * blurred picture is sent, in the hidden "redacted" field, and the file input
 * is emptied first, so the original never reaches the server.
 *
 * On an existing review the current image is loaded, so more can be blurred.
 */
(function () {
  'use strict';

  var EXPORT_WIDTH = 1600;

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    var tool = document.getElementById('lr-blur');
    var input = document.getElementById('id_source');
    var redacted = document.getElementById('id_redacted');
    var count = document.getElementById('id_blur_count');
    if (!tool || !input || !redacted || !count) return;

    // Sit right under the file field.
    var row = input.closest('.form-row') || input.parentNode;
    row.parentNode.insertBefore(tool, row.nextSibling);

    var canvas = tool.querySelector('.lr-blur-canvas');
    var status = tool.querySelector('.lr-blur-status');
    var counter = tool.querySelector('.lr-blur-count');
    var ctx = canvas.getContext('2d');
    var base = null; // the loaded picture, at its own size
    var boxes = []; // [x, y, w, h] in picture pixels
    var drag = null;
    var changed = false; // a new file or a new box since the page opened
    var form = input.form;

    function say(text) {
      status.textContent = text || '';
      status.hidden = !text;
    }

    function block() {
      return Math.max(14, Math.round(Math.max(base.width, base.height) / 48));
    }

    // Pixelate, then blur, one box of the picture on `target`.
    function hide(target, box) {
      var x = Math.max(0, Math.floor(box[0]));
      var y = Math.max(0, Math.floor(box[1]));
      var w = Math.min(base.width - x, Math.ceil(box[2]));
      var h = Math.min(base.height - y, Math.ceil(box[3]));
      if (w < 2 || h < 2) return;
      var size = block();
      var small = document.createElement('canvas');
      small.width = Math.max(1, Math.round(w / size));
      small.height = Math.max(1, Math.round(h / size));
      var sctx = small.getContext('2d');
      sctx.drawImage(target.canvas, x, y, w, h, 0, 0, small.width, small.height);
      target.save();
      target.beginPath();
      target.rect(x, y, w, h);
      target.clip();
      target.imageSmoothingEnabled = false;
      target.drawImage(small, 0, 0, small.width, small.height, x, y, w, h);
      if ('filter' in target) {
        target.imageSmoothingEnabled = true;
        target.filter = 'blur(' + Math.round(size / 2) + 'px)';
        target.drawImage(target.canvas, x, y, w, h, x, y, w, h);
        target.filter = 'none';
      }
      target.restore();
    }

    function draw() {
      if (!base) return;
      ctx.drawImage(base, 0, 0);
      boxes.forEach(function (box) {
        hide(ctx, box);
      });
      ctx.save();
      ctx.lineWidth = Math.max(2, base.width / 400);
      ctx.setLineDash([ctx.lineWidth * 4, ctx.lineWidth * 3]);
      ctx.strokeStyle = '#e8710a';
      boxes.forEach(function (box) {
        ctx.strokeRect(box[0], box[1], box[2], box[3]);
      });
      if (drag && drag.box) {
        ctx.fillStyle = 'rgba(232, 113, 10, 0.25)';
        ctx.fillRect(drag.box[0], drag.box[1], drag.box[2], drag.box[3]);
        ctx.strokeRect(drag.box[0], drag.box[1], drag.box[2], drag.box[3]);
      }
      ctx.restore();
      counter.textContent = boxes.length + (boxes.length === 1 ? ' box' : ' boxes');
      count.value = String(boxes.length);
    }

    function show(picture) {
      base = picture;
      canvas.width = picture.width;
      canvas.height = picture.height;
      boxes = [];
      tool.hidden = false;
      say('');
      draw();
    }

    function load(url, revoke) {
      var picture = new Image();
      picture.onload = function () {
        if (revoke) URL.revokeObjectURL(url);
        show(picture);
      };
      picture.onerror = function () {
        say('That file could not be shown. Try a JPG, PNG or PDF.');
      };
      picture.src = url;
    }

    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      if (!file) return;
      changed = true;
      tool.hidden = false;
      if (file.type === 'application/pdf' || /\.pdf$/i.test(file.name)) {
        say('Opening the first page of the PDF…');
        var body = new FormData();
        body.append('file', file);
        var token = form.querySelector('[name=csrfmiddlewaretoken]');
        fetch(tool.getAttribute('data-preview-url'), {
          method: 'POST',
          body: body,
          credentials: 'same-origin',
          headers: token ? { 'X-CSRFToken': token.value } : {},
        })
          .then(function (response) {
            if (!response.ok) {
              return response.json().then(function (data) {
                throw new Error(data.error || 'That PDF could not be read.');
              });
            }
            return response.blob();
          })
          .then(function (blob) {
            load(URL.createObjectURL(blob), true);
          })
          .catch(function (error) {
            say(error.message || 'That PDF could not be read.');
          });
      } else {
        load(URL.createObjectURL(file), true);
      }
    });

    var current = tool.getAttribute('data-current');
    if (current) load(current, false);

    function point(event) {
      var rect = canvas.getBoundingClientRect();
      return [
        ((event.clientX - rect.left) / rect.width) * canvas.width,
        ((event.clientY - rect.top) / rect.height) * canvas.height,
      ];
    }

    canvas.addEventListener('pointerdown', function (event) {
      if (!base) return;
      event.preventDefault();
      canvas.setPointerCapture(event.pointerId);
      drag = { start: point(event), box: null };
    });
    canvas.addEventListener('pointermove', function (event) {
      if (!drag) return;
      var end = point(event);
      var s = drag.start;
      drag.box = [Math.min(s[0], end[0]), Math.min(s[1], end[1]), Math.abs(end[0] - s[0]), Math.abs(end[1] - s[1])];
      draw();
    });
    function finish() {
      if (!drag) return;
      if (drag.box && drag.box[2] > 4 && drag.box[3] > 4) {
        boxes.push(drag.box);
        changed = true;
      }
      drag = null;
      draw();
    }
    // Released anywhere, even outside the picture, the box is kept.
    window.addEventListener('pointerup', finish);
    window.addEventListener('mouseup', finish);
    canvas.addEventListener('pointercancel', finish);
    canvas.addEventListener('lostpointercapture', finish);

    tool.addEventListener('click', function (event) {
      var action = event.target.getAttribute('data-action');
      if (action === 'undo') boxes.pop();
      if (action === 'clear') boxes = [];
      if (action) draw();
    });

    // On save: send only the blurred picture, never the original file.
    form.addEventListener('submit', function () {
      if (base && changed) {
        var scale = Math.min(1, EXPORT_WIDTH / base.width);
        var out = document.createElement('canvas');
        out.width = Math.round(base.width * scale);
        out.height = Math.round(base.height * scale);
        var octx = out.getContext('2d');
        var work = document.createElement('canvas');
        work.width = base.width;
        work.height = base.height;
        var wctx = work.getContext('2d');
        wctx.drawImage(base, 0, 0);
        boxes.forEach(function (box) {
          hide(wctx, box);
        });
        octx.drawImage(work, 0, 0, out.width, out.height);
        redacted.value = out.toDataURL('image/jpeg', 0.9);
      }
      input.value = '';
    });
  });
})();
