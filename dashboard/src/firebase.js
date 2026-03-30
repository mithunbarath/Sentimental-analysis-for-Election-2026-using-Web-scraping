import { initializeApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyD3JyXj5YWgbTes2tdQ-6qXNzDJcgdCV3s",
  authDomain: "webscraper-508e8.firebaseapp.com",
  projectId: "webscraper-508e8",
  storageBucket: "webscraper-508e8.firebasestorage.app",
  messagingSenderId: "467028798443",
  appId: "1:467028798443:web:6d7df72c03d948d64d87ae",
  measurementId: "G-HCS56R7047"
};

const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
