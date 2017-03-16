$(document).ready(function(){
  var inputArr = window.folders;
  var appMounter = $("#appHolder");
  var model = {
    id: 'id',
    name: 'title',
    contents: 'sub_folders',
    fileUrl: 'url',
    files: 'images',
    rootfolderId: 'rootfolder',
    parentId:'parentId',
  };
  var inputMap = {};
  var curSelId = '';
  var doc = $(document);
  var folderMarkup = document.getElementById('folderstructure').innerHTML.toString();
  var fileMarkup = document.getElementById('filestructure').innerHTML.toString();
  var imgPreviewMarkup = document.getElementById('imgpreviewstructure').innerHTML.toString();
  var imageSearchViewMarkup = document.getElementById('imageSearchView').innerHTML.toString();

  String.prototype.interpolate = function (o) {
      return this.replace(/<<([^<>]*)>>/g,
          function (a, b) {
              var r = o[b];
              return typeof r === 'string' || typeof r === 'number' ? r : a;
          }
      );
  };

  function isFile(item){
    return (item && item[model.fileUrl]);
  }

  function getInterpolateableObj(item){
    return {
      name: item[model.name],
      fileUrl: item[model.fileUrl],
      id: item[model.id]
    }
  }

  function getMarkup(item) {
    if(!item) {
      return '';  
    }
    var o = getInterpolateableObj(item);
    if(isFile(item)){
      return fileMarkup.interpolate(o);
    }
    return folderMarkup.interpolate(o)
  }

  function getIndexFromParent(srcPid, sourceId, type) {
    var srcParentContents = inputMap[srcPid][type] || [];
    var srcIndex = -1;
    for(var i=0;i<srcParentContents.length;i++) {
      var item = srcParentContents[i];
      if(item.id === sourceId) {
        srcIndex = i;
        break;
      }
    }
    return srcIndex;
  }

  function removeItemFromInputMap(srcPid, sourceId, type) {
    var srcParentContents = inputMap[srcPid][type] || [];
    var srcIndex = getIndexFromParent(srcPid,sourceId, type);
    if(srcIndex > -1) {
      srcParentContents.splice(srcIndex,1);
      inputMap[srcPid][type] = srcParentContents;
    }
    return srcIndex;
  }

  function stripEntityType(str){
    if(!str) return;
    return (str.replace("folder_", "").replace("file_", ""))
  }
  function getCookie(name) {
      var cookieValue = null;
      if (document.cookie && document.cookie !== '') {
          var cookies = document.cookie.split(';');
          for (var i = 0; i < cookies.length; i++) {
              var cookie = jQuery.trim(cookies[i]);
              if (cookie.substring(0, name.length + 1) === (name + '=')) {
                  cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                  break;
              }
          }
      }
      return cookieValue;
  }

  function updateInputMapData(sourceId, targetId, type, successCB) {
    var srcContents = inputMap[sourceId];
    var srcPid = srcContents[model.parentId];
    if(sourceId === srcPid){
      return false;
    }

    if(!srcPid){
      srcPid = sourceId;
    }
    var data = { 
      "source_id": (stripEntityType(sourceId)),
      "target_id": (stripEntityType(targetId)),
      "source_type": ((type==model.files) ? 'image' : 'folder')
    };
    toggleLoader(true);
    $.ajax({
      method: "POST",
      url: "/cms/images/custom-api/folders/move/",
      data: data,
      headers:{
        'X-CSRFToken': getCookie('csrftoken')
      }
    })
    .done(function( resp, msg, jQXHR ) {
      if(jQXHR.status === 202){
        alert(resp.message);
        handleDuplicateEntityCreation(resp, targetId);
        return;
      }
      srcContents[model.name] = resp.data.title;
      if(!targetId) {
        inputMap[sourceId][model.parentId] = model.rootfolderId;
        inputArr.push(inputMap[sourceId]);
      } else{
        var targetContents = inputMap[targetId][type] || [];
        removeItemFromInputMap(srcPid, sourceId, type);
        inputMap[sourceId][model.parentId] = targetId;
        targetContents.push(srcContents);
        inputMap[targetId][type] = targetContents;
      }
        if(successCB){successCB(resp)}
    }).complete(function(){
      toggleLoader(false);
    });
  }

  function checkIfEntityWithNameExists(srcId, targetId) {
    var srcContents = inputMap[srcId];
    var targetContents = inputMap[targetId];
    var srcTitle = srcContents[model.name];
    var isEntityFile = isFile(srcContents);
    var entity = targetContents[(isEntityFile ? model.files : model.contents)] || [];
    for(var i=0;i<entity.length;i++) {
      if(entity[i][model.name] === srcTitle){
        return true;
      }
    }
    return false;
  }

  function createFolderHTML(obj) {
    var html;
    if(obj instanceof Array){
      html = ''
      for(var i=0;i<obj.length;i++) {
        html += getMarkup(obj[i]);
      }
    } else {
      var images = obj[model.files] || [];
      var subFolders = obj[model.contents] || [];
      html = '';
      for(var i=0;i<subFolders.length;i++) {
        html += getMarkup(subFolders[i]);
      }
      for(var i=0;i<images.length;i++) {
        html += getMarkup(images[i]);
      }
    }
    try {
      $(".droppable").droppable("destroy");
      $(".draggable").draggable("destroy");
    } catch(e){}
    if(html){
      appMounter.append('<div class="entity-wrapper" data-content-id="'+(obj[model.id] || model.rootfolderId)+'">'+html+'</div>');
    }
    $(".draggable").draggable({revert: true, snap: 'inner', scroll: false,zIndex: 999 });
    $(".droppable, .entity-wrapper").droppable({
      greedy: true,
      hoverClass: "ui-state-active",
      drop: function( event, ui ) {
        event.stopPropagation();
        var targetId = this.getAttribute('data-content-id') || "";
        if(targetId === model.rootfolderId) return;
        var srcEl = $(ui.helper[0]);
        if(srcEl.length === 0) return;
        var sourceId =  srcEl.attr('data-content-id') || '';
        if(sourceId === targetId){
          alert("Cannot drop the folder into itself");
          return
        }
        var srcPid = inputMap[sourceId][model.parentId];
        if(srcPid === targetId) return;
        var type = model.files;
        if(srcEl.hasClass('droppable')) {
          type = model.contents;
        }
        updateInputMapData(sourceId, targetId, type, function(){
        srcEl.remove();
        if(targetId === model.rootfolderId) {
        var _this = $(this);
        clearFolderSelectedClass();
        addFolderSelectedClass(_this);
        clearWrapperSiblings(_this);
        appMounter.html('');
        var obj = inputMap[model.rootfolderId];
        createFolderHTML(obj);
        } else{
          $("[data-content-id="+(targetId)+"]").click();
        }
      });
      }
    });
  }

  function deleteCurrSelectedItem(){
    if(!curSelId) return;
    var srcContents = inputMap[curSelId];
    var entityIsFile = isFile(srcContents);
    var r = confirm("Are you sure you want to delete this " +(entityIsFile ? "image?" : "folder?"));
    if (r === false) {
       return
    }
    toggleLoader(true);
    $.ajax({
      method: "POST",
      url: "/cms/images/custom-api/"+(entityIsFile ? "images" : "folders")+"/"+stripEntityType(curSelId)+"/delete/",
      headers:{
        'X-CSRFToken': getCookie('csrftoken')
      }
    })
    .done(function( msg ) {
      var srcPid = srcContents[model.parentId];
      var el = $("[data-content-id="+curSelId+"]");
      var type = isFile(srcContents) ? model.files : model.contents;
      var srcIndex = removeItemFromInputMap(srcPid, curSelId, type);
      if(srcIndex > -1) {
        el.remove();
      }

    }).complete(function(){
      toggleLoader(false);
    });
  }

  function renameCurrSelectedItem(){
    if(!curSelId) return;
    var inputEl = $("[data-content-id="+curSelId+"] input.editableInput");
    inputEl.removeAttr('readonly').focus();
    inputEl.attr("original-name", inputEl.val());
  }

  function createMapFromArray(content, pid) {
    if(!content) return;
    for(var i=0;i<content.length;i++) {
      var o = content[i];
      if(o) {
        var item = o[model.contents];
        var files = o[model.files];
        var id = o[model.id];
        var obj = {};
        obj[model.parentId] = (pid || model.rootfolderId);
        var keys = Object.keys(o);
        for(var j=0;j<keys.length;j++){
          var k = keys[j];
          if(k === model.id) {
            obj[k] = o[k];
          } else{
            obj[k] = o[k];
          }
        }
        inputMap[id] = Object.assign({}, obj);
        if(item && item.length > 0){
          createMapFromArray(item, id);
        }
        if(files && files.length > 0){
          createMapFromArray(files, id);
        }
      }
    }
  }

  function createInitialMapFromArray(input) {
    var o = {}
    o[model.id] = model.rootfolderId;
    o[model.contents] = [];
    o[model.files] = [];
    for(var i=0;i<input.length;i++) {
      var item = input[i];
      var content = item[model.contents];
      var files = item[model.files];
      if(content || files) {
        o[model.contents].push(item);
      } else{
        o[model.files].push(item);
      }
    }
    inputMap[model.rootfolderId] = o;
  }
  function appendEntityTypeForId(content, entityType, pid) {
    if(!content) return;
    for(var i=0;i<content.length;i++) {
      var o = content[i];
      if(o) {
        var item = o[model.contents];
        var files = o[model.files];
        var id = o[model.id] = (entityType || "")+o[model.id];
        if(o[model.parentId] === undefined) {
          o[model.parentId] = pid;
        }
        if(item && item.length > 0){
          appendEntityTypeForId(item, "folder_", id);
        }
        if(files && files.length > 0){
          appendEntityTypeForId(files, "file_", id);
        }
      }
    }
    return content;
  }

  function init(){
    appendEntityTypeForId(inputArr);
    createInitialMapFromArray(inputArr);
    createMapFromArray(inputArr);
    createFolderHTML(inputArr);
    $("[data-content-id='-1']").click().hide();
  }

  function clearWrapperSiblings(el) {
    if(!el) return;
    var wrapper = el.closest('.entity-wrapper');
    var siblings = wrapper.next();
    var sibArr = [];
    while(siblings.length > 0) {
      sibArr.push(siblings);
      siblings = siblings.next();
    }
    for(var i=0;i<sibArr.length;i++) {
      sibArr[i].remove();
    }
  }

  function highlightParentFolders(id){
    var pid = inputMap[id][model.parentId];
    var parEl = $(".contentID[data-content-id="+pid+"]");
    if(parEl.length === 0) {
      return;
    }
    if(pid !== model.rootfolderId) {
      parEl.addClass('folder_selected_path');
    }
    highlightParentFolders(pid);
  }

  function clearFolderSelectedClass(){
    $(".folder_selected").removeClass("folder_selected");
    $(".folder_selected_path").removeClass("folder_selected_path");
  }

  function addFolderSelectedClass(el){
    if(!el || !el.hasClass('contentID')) return;
    var id = el.attr('data-content-id');
    el.addClass("folder_selected");
    highlightParentFolders(id);
  }

  function uploadFile(){
    $("#fileUpload").click();
  }

  doc.on('click', '.contentID', function(){
    var _this = $(this);
    clearFolderSelectedClass();
    addFolderSelectedClass(_this);
    var id = _this.attr('data-content-id');
    clearWrapperSiblings(_this);
    var obj = inputMap[id];
    if(isFile(obj)){
      var o = getInterpolateableObj(obj);
      o[model.id] = stripEntityType(o[model.id]);
      appMounter.append(imgPreviewMarkup.interpolate(o));
      return;
    } else{
      $(".imgPreview").remove();
      createFolderHTML(obj);
    }
  });

  function hideMenuOptionsForFile(id){

    if(isFile(inputMap[id])) {
      $("[data-hide=file]").hide();
    } else{
      $("[data-hide=file]").show();
    }
  }

  function hideMenuOptionsForWrapper(el){
    if(el.hasClass('entity-wrapper')){
      $('[data-hide="wrapper"]').hide();
    } else{
      $('[data-hide="wrapper"]').show();
    }
  }

  doc.on("contextmenu", "[data-content-id]", function(e){
    var _this = $(this);
    e.preventDefault();
    e.stopPropagation();
    var id = _this.attr('data-content-id');
    if( id === "rootfolder") {
      return;
    }
    hideMenuOptionsForWrapper(_this);
    hideMenuOptionsForFile(id);
    clearWrapperSiblings(_this);
    clearFolderSelectedClass();
    addFolderSelectedClass(_this);
    $(".custom_contextmenu").css({'display':'block','left':e.pageX+'px', 'top':e.pageY+'px'});
    curSelId = id;
  });

  $(".custom_contextmenu a").click(function(){
    var _this = $(this);
    var action = _this.attr('data-action');
    switch(action) {
      case 'delete':
        deleteCurrSelectedItem();
        break;
      case 'rename':
        renameCurrSelectedItem();
        break;
      case 'newfile':
        uploadFile();
        break;
      case 'newfolder':
        createNewFolder();
        break;
      default: break;
    }
  });

  $("#fileUpload").change(function(evt){
    var data = new FormData();
    $.each(evt.target.files, function(key, value){
        data.append("files[]", value);
    });
    data.append("folder_id", stripEntityType(curSelId));
    toggleLoader(true);
     $.ajax({
       url: '/cms/images/custom-api/images/add/',
       type: 'POST',
       data: data,
       async: false,
       cache: false,
       contentType: false,
        headers:{
          'X-CSRFToken': getCookie('csrftoken')
        },
       enctype: 'multipart/form-data',
       processData: false,
       success: function (resp) {
        var hasFiles = inputMap[curSelId][model.files];
        var arr = appendEntityTypeForId([Object.assign({}, resp.data)], "file_", curSelId);

        var obj = Object.assign({}, arr[0]);
        createMapFromArray(arr, obj[model.id]);
        inputMap[obj[model.id]] = Object.assign({}, obj)
        if(hasFiles){
          inputMap[curSelId][model.files].push(obj);
        } else{
          inputMap[curSelId][model.files] = [obj];
        }
        var el = $("[data-content-id="+curSelId+"]");
        clearWrapperSiblings(el);
        createFolderHTML(inputMap[curSelId])

       },
       error:function(response) {
        if(response.responseJSON && response.responseJSON.message) {
          alert(response.responseJSON.message)
        }
      },
      complete: function(r){
        toggleLoader(false);
        this.value = null;
      }
     });
  });

  function toggleLoader(opt) {
    if(opt === true){
      $("#mainCntr #spinner").show();
    } else{
      $("#mainCntr #spinner").hide();
    }
  }
  function createNewFolder(){
    $("#mainCntr .modalBg").show().find("#newfolderId").focus();
  }
  doc.on('click', '#mainCntr #cancelBtn', function(){
    $("#newfolderId").val("");
    $("#mainCntr .modalBg").hide();
  });
  doc.on('keypress', "#mainCntr #newfolderId", function(){
    if(event.keyCode === 13) {
      $('#mainCntr #newfolderBtn').click();
    }
  })
  doc.on('click', '#mainCntr #newfolderBtn', function(){
    var folderName = $("#newfolderId").val();
    var _this = $(this);
    _this.attr("disabled", true);
    toggleLoader(true);
    $.ajax({
      method: "POST",
      url: "/cms/images/custom-api/folders"+(curSelId === "-1" ? "" : ("/"+stripEntityType(curSelId)))+"/add/",
      "data":{
        title: folderName
      },
      headers:{
        'X-CSRFToken': getCookie('csrftoken')
      }
    })
    .done(function( resp, msg, jQXHR ) {
      clearWrapperSiblings($("[data-content-id="+curSelId+"]"));
      if(jQXHR.status === 202){
        alert(resp.message);
        handleDuplicateEntityCreation(resp, curSelId);
        return;
      }
      var hasFolders = inputMap[curSelId][model.contents];
      var arr = appendEntityTypeForId([Object.assign({}, resp.data)], "folder_", curSelId);

      var obj = Object.assign({}, arr[0]);
      createMapFromArray(arr, obj[model.id]);
      inputMap[obj[model.id]] = Object.assign({}, obj)
      if(hasFolders){
        inputMap[curSelId][model.contents].push(obj);
      } else{
        inputMap[curSelId][model.contents] = [obj];
      }
      createFolderHTML(inputMap[curSelId])

    })
    .error(function(resp, jQXHR){
      if(resp.responseJSON && resp.responseJSON.message) {
        alert(resp.responseJSON.message)
      }
    })
    .complete(function(){
      toggleLoader(false);
      _this.attr("disabled", false);
      $("#newfolderId").val("");
      $("#mainCntr .modalBg").hide();
    });
  });

  doc.click(function(e){
    var ctxMenu = $(".custom_contextmenu");
    if(ctxMenu.is(':visible')) {
      ctxMenu.hide();
      $(".folder_selected").removeClass("folder_selected");
    }
  });

  $("#fileSearchField").val('').keypress(function(){
    if(event.keyCode === 13) {
      var val = $(this).val().trim();
      if(!val){
         $("#clearSearchBtn").hide();
        return;
      } else{
         $("#clearSearchBtn").show();
      }
      toggleLoader(true);
       $.ajax({
        method: "GET",
        url: "/cms/images/custom-api/images/search/",
        data:{
          'query_string': val
        }
      }).done(function( resp, msg, jQXHR ) {
        var html = '';
        if(resp.length === 0) {
          html = '<span class="noresults">No Results Found</span>';
        } else{
          for(var i=0;i<resp.length;i++) {
            var o = getInterpolateableObj(resp[i]);
            html += imageSearchViewMarkup.interpolate(o);
          }
        }
        if(html){
          $("#appHolder").hide();
          $("#searchResultsHolder").html(html).show();
        }
      }).complete(function(){
        toggleLoader(false);
      })
    }
  });

  function handleDuplicateEntityCreation(resp, targetId){
    var isEntityFile = isFile(inputMap[targetId]);
    var respObj = Object.assign({}, resp.data);
    var entity = isEntityFile ? "file_" :"folder_";
    var id = entity+respObj[model.id];
    var pid = targetId;
    var arr = appendEntityTypeForId([respObj], entity, pid);

    var obj = Object.assign({}, arr[0]);
    createMapFromArray(arr, obj[model.id]);
    inputMap[obj[model.id]] = Object.assign({}, obj);
    var hasFolders = inputMap[pid][model.contents];
    if(hasFolders){
      inputMap[pid][model.contents].push(obj);
    } else{
      inputMap[pid][model.contents] = [obj];
    }
    createFolderHTML(inputMap[pid]);
    $("[data-content-id="+pid+"].contentID").click();
  }

  $("#clearSearchBtn").click(function(){
    $("#fileSearchField").val('');
    $("#appHolder").show();
    $("#searchResultsHolder").html('').hide();
    $(this).hide();
  }).hide();

  doc.on("blur", ".contentID input.editableInput", function(){
    var _this = $(this);
    if(_this.attr("readonly")) return;
    _this.attr("readonly", "readonly");
    if(!curSelId) return;
    var isEntityFile = isFile(inputMap[curSelId]);
    var changedName = _this.val();
    _this.val(_this.attr("original-name"));
    toggleLoader(true);
    $.ajax({
      method: "POST",
      url: "/cms/images/custom-api/"+(isEntityFile ? "images" : "folders")+"/"+stripEntityType(curSelId)+"/edit/",
      data:{
        'title': changedName
      },
      headers:{
        'X-CSRFToken': getCookie('csrftoken')
      }
    }).done(function( resp, msg, jQXHR ) {
      if(jQXHR.status === 202){
        alert(resp.message);
        var targetId = inputMap[curSelId][model.parentId];
        handleDuplicateEntityCreation(resp,targetId);
        return;
      }
      else{
        var title = resp.data.title;
        _this.val(title);
        var srcPid = inputMap[curSelId][model.parentId];
        if(!srcPid) {
          inputMap[curSelId][model.name] = title;
          return;
        }
        var el = $("[data-content-id="+curSelId+"]");
        var contentKey = (isEntityFile ? model.files : model.contents);
        var ind = getIndexFromParent(srcPid, curSelId, contentKey);
        var srcParentContents = inputMap[srcPid][contentKey] || [];
        srcParentContents[ind][model.name] = inputMap[curSelId][model.name] = title;
      }
    })
    .error(function(resp, jQXHR){
      if(resp.responseJSON && resp.responseJSON.message) {
        alert(resp.responseJSON.message)
      }else{
        if(resp.statusText && typeof resp.statusText === "string"){
          alert(resp.statusText)
        }
      }
    }).complete(function(){
      toggleLoader(false);
      _this.attr('readonly', 'readonly');
    });

  });


  init();
})