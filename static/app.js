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
document.addEventListener('DOMContentLoaded', function() {
  const checkbox = document.getElementById('postContent');
  const hiddenInput = document.getElementById('postContentHidden');

  // Initial check to set the hidden input value based on the checkbox's state
  hiddenInput.value = checkbox.checked ? '1' : '0';

  checkbox.addEventListener('change', function() {
      // When the checkbox state changes, update the hidden input accordingly
      hiddenInput.value = this.checked ? '1' : '0';
  });
});

function addInput(arrayName) {
  const newInput = document.createElement('input');
  newInput.type = 'text';
  newInput.name = arrayName+'[]';
  newInput.setAttribute('aria-label', arrayName);
  
  const lineBreak = document.createElement('br');

  const container = document.getElementById(arrayName+'Container');
  
  container.appendChild(newInput);
  container.appendChild(lineBreak);
}