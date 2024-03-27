/* scobiform.com 2024 */

// Create WebSocket connection
const socket = new WebSocket('ws://' + window.location.host + '/ws');
      
// Connection opened
socket.addEventListener('open', function (event) {
  socket.send('CAT connected...'); // Send a message to the server
});

// Listen for messages
socket.addEventListener('message', function (event) {
  //console.log('Message from server ', event.data);
  document.getElementById('messages').innerHTML += event.data;
  //scrollToBottom();
});

function scrollToBottom() {
  var messagesDiv = document.getElementById('messages');
  //console.log(messagesDiv.scrollHeight);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

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

// Lazy load images
document.addEventListener("DOMContentLoaded", function() {
  var lazyLoadImages = document.querySelectorAll('img.lazy-load');
  var imageObserver = new IntersectionObserver(function(entries, observer) {
      entries.forEach(function(entry) {
          if (entry.isIntersecting) {
              var image = entry.target;
              image.src = image.dataset.src;
              image.classList.remove('lazy-load');
              imageObserver.unobserve(image);
          }
      });
  });

  lazyLoadImages.forEach(function(image) {
      imageObserver.observe(image);
  });
});
