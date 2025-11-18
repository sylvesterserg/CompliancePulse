(function () {
  function closestAttr(element, attr) {
    return element ? element.closest("[" + attr + "]") : null;
  }

  function getTarget(element) {
    var selector = element.getAttribute("hx-target");
    if (selector) {
      return document.querySelector(selector);
    }
    return element;
  }

  function applySwap(target, swapType, html) {
    if (!target) return;
    if (swapType === "outerHTML") {
      target.outerHTML = html;
    } else {
      target.innerHTML = html;
    }
  }

  function processOutOfBand(doc) {
    var nodes = doc.querySelectorAll("[hx-swap-oob]");
    nodes.forEach(function (node) {
      var swapType = node.getAttribute("hx-swap-oob") || "innerHTML";
      if (node.id) {
        var target = document.getElementById(node.id);
        if (target) {
          applySwap(target, swapType, node.innerHTML);
        }
      }
      node.remove();
    });
  }

  function request(element, method, url, body) {
    var target = getTarget(element);
    if (!target || !url) return;
    var headers = {
      "HX-Request": "true",
      "X-Requested-With": "XMLHttpRequest",
      Accept: "text/html",
    };
    var options = { method: method, headers: headers };
    if (body) {
      options.body = body;
    }
    fetch(url, options)
      .then(function (response) {
        return response.text();
      })
      .then(function (html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, "text/html");
        processOutOfBand(doc.body);
        var swapType = element.getAttribute("hx-swap") || "innerHTML";
        applySwap(target, swapType, doc.body.innerHTML);
      })
      .catch(function (error) {
        console.error("HTMX-lite request failed", error);
      });
  }

  document.addEventListener("click", function (event) {
    var trigger = closestAttr(event.target, "hx-get") || closestAttr(event.target, "hx-post");
    if (!trigger) {
      return;
    }
    var method = trigger.hasAttribute("hx-post") ? "POST" : "GET";
    var url = trigger.getAttribute(method === "POST" ? "hx-post" : "hx-get");
    event.preventDefault();
    request(trigger, method, url);
  });

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.matches("form")) return;
    if (!form.hasAttribute("hx-post") && !form.hasAttribute("hx-get")) {
      return;
    }
    event.preventDefault();
    var method = form.hasAttribute("hx-post") ? "POST" : "GET";
    var url = form.getAttribute(method === "POST" ? "hx-post" : "hx-get");
    var formData = new FormData(form);
    var body = null;
    if (method === "POST") {
      body = formData;
    } else if (url) {
      var params = new URLSearchParams(formData).toString();
      url += url.indexOf("?") === -1 ? "?" + params : "&" + params;
    }
    request(form, method, url, body);
  });
})();
