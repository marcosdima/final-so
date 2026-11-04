import { initController } from "./modules/controller.js";

document.addEventListener("DOMContentLoaded", () => {
  const uiElements = {
    posInput: document.getElementById("logical-pos-input"),
    stepCounterText: document.getElementById("step-counter-text"),
    stepProgressFill: document.getElementById("step-progress-fill"),
    carouselTrack: document.getElementById("carousel-track"),
    carouselDots: document.getElementById("carousel-dots"),
    btnCarouselPrev: document.getElementById("carousel-prev"),
    btnCarouselNext: document.getElementById("carousel-next"),
    stepProgressLabel: document.getElementById("step-progress-label"),
    btnStepAuto: document.getElementById("btn-step-auto"),
    btnStepReset: document.getElementById("btn-step-reset"),
    simplePanel: document.getElementById("indirect-simple-panel"),
    doublePanel: document.getElementById("indirect-double-panel"),
    triplePanel: document.getElementById("indirect-triple-panel"),
    emptyPanel: document.getElementById("index-panel-empty"),
    doubleEntriesList: document.getElementById("double-panel-body"),
    tripleEntriesList: document.getElementById("triple-panel-body"),
  };
  initController(uiElements);
});
