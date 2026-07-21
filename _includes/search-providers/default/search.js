var SOURCES = window.TEXT_VARIABLES.sources;
var PAHTS = window.TEXT_VARIABLES.paths;
window.Lazyload.js(SOURCES.jquery, function() {
  var search = (window.search || (window.search = {}));
  var searchData = window.TEXT_SEARCH_DATA || {};
  var searchDataLoaded = !!window.TEXT_SEARCH_DATA;
  var searchDataLoading = false;
  var MAX_RESULTS_PER_COLLECTION = 20;
  var MAX_MATCHES_PER_ARTICLE = 3;

  function memorize(f) {
    var cache = {};
    return function () {
      var key = Array.prototype.join.call(arguments, ',');
      if (key in cache) return cache[key];
      else return cache[key] = f.apply(this, arguments);
    };
  }

  /// search
  function searchByQuery(query) {
    var i, j, key, keys, cur, title, content, lines, lineIndex;
    var normalizedQuery = query.trim().toLocaleLowerCase();
    var result = {};
    if (!normalizedQuery) { return result; }

    keys = Object.keys(searchData);
    for (i = 0; i < keys.length; i++) {
      key = keys[i];
      for (j = 0; j < searchData[key].length; j++) {
        if (result[key] && result[key].length >= MAX_RESULTS_PER_COLLECTION) {
          break;
        }

        cur = searchData[key][j];
        title = cur.title || '';
        content = cur.content || '';
        lines = content.split(/\r?\n/);

        if (title.toLocaleLowerCase().indexOf(normalizedQuery) >= 0) {
          addResult(result, key, cur, null, null);
        }

        var articleMatches = 0;
        for (lineIndex = 0; lineIndex < lines.length; lineIndex++) {
          if (result[key] && result[key].length >= MAX_RESULTS_PER_COLLECTION
              || articleMatches >= MAX_MATCHES_PER_ARTICLE) {
            break;
          }
          var line = lines[lineIndex].trim();
          if (isSearchableLine(line)
              && line.toLocaleLowerCase().indexOf(normalizedQuery) >= 0) {
            addResult(result, key, cur, line, lineIndex + 1);
            articleMatches++;
          }
        }
      }
    }
    return result;
  }

  function addResult(result, key, article, line, lineNumber) {
    if (result[key] === undefined) {
      result[key] = [];
    }
    result[key].push({
      title: article.title,
      url: article.url,
      line: line,
      lineNumber: lineNumber
    });
  }

  function isSearchableLine(line) {
    return line && !/^!\[[^\]]*\]\([^)]*\)\s*$/.test(line);
  }

  var renderHeader = memorize(function(header) {
    return $('<p class="search-result__header"></p>').text(header);
  });

  function appendHighlightedText($element, value, query) {
    var normalizedValue = value.toLocaleLowerCase();
    var normalizedQuery = query.toLocaleLowerCase();
    var cursor = 0;
    var matchIndex = normalizedValue.indexOf(normalizedQuery);
    while (matchIndex >= 0) {
      $element.append(document.createTextNode(value.slice(cursor, matchIndex)));
      $('<mark class="search-result__mark"></mark>')
        .text(value.slice(matchIndex, matchIndex + query.length))
        .appendTo($element);
      cursor = matchIndex + query.length;
      matchIndex = normalizedValue.indexOf(normalizedQuery, cursor);
    }
    $element.append(document.createTextNode(value.slice(cursor)));
  }

  var renderItem = function(index, item, query) {
    var $item = $('<li class="search-result__item"></li>').attr('data-index', index);
    var $link = $('<a class="button"></a>').attr('href', item.url).appendTo($item);
    var $title = $('<span class="search-result__title"></span>').appendTo($link);
    appendHighlightedText($title, item.title, query);
    if (item.line) {
      var $line = $('<span class="search-result__line"></span>').appendTo($link);
      $('<span class="search-result__line-number"></span>')
        .text('L' + item.lineNumber)
        .appendTo($line);
      var $snippet = $('<span class="search-result__snippet"></span>').appendTo($line);
      appendHighlightedText($snippet, item.line, query);
    }
    return $item;
  };

  function render(data, query) {
    if (!data) { return null; }
    var $root = $('<ul></ul>'), i, j, key, keys, cur, itemIndex = 0;
    keys = Object.keys(data);
    for (i = 0; i < keys.length; i++) {
      key = keys[i];
      $root.append(renderHeader(key));
      for (j = 0; j < data[key].length; j++) {
        cur = data[key][j];
        $root.append(renderItem(itemIndex++, cur, query.trim()));
      }
    }
    return $root;
  }

  // search box
  var $result = $('.js-search-result'), $resultItems;
  var lastActiveIndex, activeIndex;

  function clear() {
    $result.html(null);
    $resultItems = $('.search-result__item'); activeIndex = 0;
  }

  function renderQuery(val) {
    $result.html(render(searchByQuery(val), val));
    $resultItems = $('.search-result__item'); activeIndex = 0;
    $resultItems.eq(0).addClass('active');
  }

  function onInputNotEmpty(val) {
    if (searchDataLoaded) {
      renderQuery(val);
    } else if (!searchDataLoading) {
      searchDataLoading = true;
      window.Lazyload.js(PAHTS.search_js, function() {
        searchData = window.TEXT_SEARCH_DATA || {};
        searchDataLoaded = true;
        searchDataLoading = false;
        var currentVal = search.getVal && search.getVal();
        if (currentVal) {
          renderQuery(currentVal);
        } else {
          clear();
        }
      });
    }
  }

  search.clear = clear;
  search.onInputNotEmpty = onInputNotEmpty;

  function updateResultItems() {
    lastActiveIndex >= 0 && $resultItems.eq(lastActiveIndex).removeClass('active');
    activeIndex >= 0 && $resultItems.eq(activeIndex).addClass('active');
  }

  function moveActiveIndex(direction) {
    var itemsCount = $resultItems ? $resultItems.length : 0;
    if (itemsCount > 1) {
      lastActiveIndex = activeIndex;
      if (direction === 'up') {
        activeIndex = (activeIndex - 1 + itemsCount) % itemsCount;
      } else if (direction === 'down') {
        activeIndex = (activeIndex + 1 + itemsCount) % itemsCount;
      }
      updateResultItems();
    }
  }

  // Char Code: 13  Enter, 37  ⬅, 38  ⬆, 39  ➡, 40  ⬇
  $(window).on('keyup', function(e) {
    var modalVisible = search.getModalVisible && search.getModalVisible();
    if (modalVisible) {
      if (e.which === 38) {
        modalVisible && moveActiveIndex('up');
      } else if (e.which === 40) {
        modalVisible && moveActiveIndex('down');
      } else if (e.which === 13) {
        modalVisible && $resultItems && activeIndex >= 0 && $resultItems.eq(activeIndex).children('a')[0].click();
      }
    }
  });

  $result.on('mouseover', '.search-result__item > a', function() {
    var itemIndex = $(this).parent().data('index');
    itemIndex >= 0 && (lastActiveIndex = activeIndex, activeIndex = itemIndex, updateResultItems());
  });
});
