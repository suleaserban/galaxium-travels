import { useState } from 'react';
import type { Flight, SeatClass, ErrorResponse } from '../../types';
import { Modal, Button } from '../common';
import { Plane, Calendar, Clock, DollarSign } from 'lucide-react';
import {
  formatCurrency,
  formatDate,
  calculateDuration,
  SEAT_CLASS_LABELS,
  getSeatClass,
} from '../../utils/formatters';
import { bookFlight, isErrorResponse } from '../../services/api';
import { useUser } from '../../hooks/useUser';
import toast from 'react-hot-toast';

interface BookingModalProps {
  isOpen: boolean;
  onClose: () => void;
  flight: Flight | null;
  onSuccess: () => void;
}

export const BookingModal = ({ isOpen, onClose, flight, onSuccess }: BookingModalProps) => {
  const { user } = useUser();
  const [isLoading, setIsLoading] = useState(false);
  const [chosenClass, setChosenClass] = useState<SeatClass | null>(null);

  if (!flight) return null;

  const classOptions = (Object.keys(SEAT_CLASS_LABELS) as SeatClass[])
    .map((seatClass) => getSeatClass(flight, seatClass))
    .filter((sc) => sc !== undefined);
  const isAvailable = (seatClass: SeatClass | null) =>
    classOptions.some((sc) => sc.seat_class === seatClass && sc.seats_available > 0);
  // Keep the user's choice while it is bookable on this flight; otherwise default to the first available class
  const selectedClass = isAvailable(chosenClass)
    ? chosenClass
    : classOptions.find((sc) => sc.seats_available > 0)?.seat_class ?? null;
  const selectedOption = classOptions.find((sc) => sc.seat_class === selectedClass);

  const handleClose = () => {
    setChosenClass(null);
    onClose();
  };

  const handleConfirmBooking = async () => {
    if (!user) {
      toast.error('Please sign in to book a flight');
      return;
    }
    if (!selectedClass) {
      toast.error('Please select a seat class');
      return;
    }

    setIsLoading(true);

    try {
      const result = await bookFlight({
        user_id: user.user_id,
        name: user.name,
        flight_id: flight.flight_id,
        seat_class: selectedClass,
      });

      if (isErrorResponse(result)) {
        toast.error(result.details || result.error);
        return;
      }

      toast.success('Flight booked successfully!');
      onSuccess();
      handleClose();
    } catch (error) {
      const err = error as Partial<ErrorResponse>;
      toast.error(err.details || err.error || 'Failed to book flight');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Confirm Your Booking"
      size="md"
    >
      <div className="space-y-6">
        {/* Flight Summary */}
        <div className="glass-card p-4 bg-white/5">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-lg bg-cosmic-gradient">
              <Plane className="text-white" size={24} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-star-white">
                {flight.origin} → {flight.destination}
              </h3>
              <p className="text-sm text-star-white/60">
                Flight #{flight.flight_id}
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {/* Departure */}
            <div className="flex items-start gap-3">
              <Calendar className="text-cosmic-purple mt-1" size={20} />
              <div>
                <p className="text-xs text-star-white/60">Departure</p>
                <p className="text-star-white font-medium">
                  {formatDate(flight.departure_time)}
                </p>
              </div>
            </div>

            {/* Arrival */}
            <div className="flex items-start gap-3">
              <Calendar className="text-cosmic-purple mt-1" size={20} />
              <div>
                <p className="text-xs text-star-white/60">Arrival</p>
                <p className="text-star-white font-medium">
                  {formatDate(flight.arrival_time)}
                </p>
              </div>
            </div>

            {/* Duration */}
            <div className="flex items-start gap-3">
              <Clock className="text-cosmic-purple mt-1" size={20} />
              <div>
                <p className="text-xs text-star-white/60">Duration</p>
                <p className="text-star-white font-medium">
                  {calculateDuration(flight.departure_time, flight.arrival_time)}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Passenger Info */}
        {user && (
          <div className="glass-card p-4 bg-white/5">
            <h4 className="text-sm font-semibold text-star-white mb-2">
              Passenger Information
            </h4>
            <p className="text-star-white">{user.name}</p>
            <p className="text-star-white/60 text-sm">{user.email}</p>
          </div>
        )}

        {/* Seat Class */}
        <div className="glass-card p-4 bg-white/5">
          <h4 className="text-sm font-semibold text-star-white mb-2">Seat Class</h4>
          <div className="space-y-2" role="radiogroup" aria-label="Seat class">
            {classOptions.map((sc) => {
              const soldOut = sc.seats_available === 0;
              const isSelected = sc.seat_class === selectedClass;
              return (
                <button
                  key={sc.seat_class}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  disabled={soldOut || isLoading}
                  onClick={() => setChosenClass(sc.seat_class)}
                  className={`w-full flex items-center justify-between p-3 rounded-lg border transition-colors ${
                    isSelected
                      ? 'border-cosmic-purple bg-cosmic-purple/20'
                      : 'border-white/10 hover:border-white/30'
                  } ${soldOut ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <span className="text-star-white font-medium">
                    {SEAT_CLASS_LABELS[sc.seat_class]}
                  </span>
                  <span className="flex items-center gap-3">
                    <span className={`text-xs ${soldOut ? 'text-red-500' : 'text-star-white/60'}`}>
                      {soldOut ? 'Sold Out' : `${sc.seats_available} seats`}
                    </span>
                    <span className="text-star-white font-bold">{formatCurrency(sc.price)}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Price */}
        <div className="flex items-center justify-between p-4 glass-card bg-cosmic-gradient">
          <div className="flex items-center gap-2">
            <DollarSign className="text-white" size={24} />
            <span className="text-white font-semibold">Total Price</span>
          </div>
          <span className="text-2xl font-bold text-white">
            {selectedOption ? formatCurrency(selectedOption.price) : '—'}
          </span>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button
            variant="secondary"
            onClick={handleClose}
            disabled={isLoading}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirmBooking}
            isLoading={isLoading}
            disabled={!selectedClass}
            className="flex-1"
          >
            Confirm Booking
          </Button>
        </div>

        <p className="text-xs text-star-white/60 text-center">
          By confirming, you agree to our terms and conditions
        </p>
      </div>
    </Modal>
  );
};

// Made with Bob
