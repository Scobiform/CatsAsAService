/* scobiform.com 2024 */

// Create WebSocket connection
 const socket = new WebSocket('ws://' + window.location.host + '/ws');
        
 // Connection opened
 socket.addEventListener('open', function (event) {
     socket.send('Client connected...'); // Send a message to the server
 });
 
 // Listen for messages
 socket.addEventListener('message', function (event) {
     //console.log('Message from server ', event.data);
     document.getElementById('messages').innerHTML += event.data;
 });

 // Activate the first tab
 document.getElementsByClassName("tablinks")[0].click();

 // Open tab function
 function openTab(evt, tabName) {
    var i, tabcontent, tablinks;
    // Get all elements with class="tabcontent" and hide them
    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
      tabcontent[i].style.display = "none";
    }
    // Get all elements with class="tablinks" and remove the class "active"
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
      tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    // Show the current tab, and add an "active" class to the button that opened the tab
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";
  }

// ------------------------------------------------
// Form
// Add ui switch to the post content checkbox
